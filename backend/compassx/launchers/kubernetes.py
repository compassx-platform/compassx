"""Kubernetes Launcher — platform services in a K8s cluster.

Absorbs the platform-lifecycle logic that previously lived in
backend/services/startup.py (FastAPI lifespan):

- RBAC setup (ServiceAccount / ClusterRole / ClusterRoleBinding for EG)
- image builds + `minikube image load` (EG, airflow, notebook-runner, ingress addon images)
- kubectl apply of manifests (infrastructure + application services)
- supervised kubectl port-forwards (generic loop; the Windows-specific
  stale-listener detection/killing logic is preserved)

Minikube is treated as a standard cluster; ensure_images/port_forwards
are just profile toggles for local clusters.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from compute.config import compute_settings
from compassx.interfaces.launcher import Launcher, LauncherStatus, ServiceStatus
from compassx.models import LauncherError
from compassx.registry.profile import DeploymentProfile

logger = logging.getLogger(__name__)

_PF_LOG_PREFIX = ">>> PORT-FORWARD <<<"


# ── process/port helpers (ported from services/startup.py) ──────────────────

def _listening_pids(port: int) -> list[int]:
    """Return PIDs currently listening on *port*."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                [
                    "powershell",
                    "-NonInteractive",
                    "-Command",
                    (
                        f"Get-NetTCPConnection -State Listen -LocalPort {port} "
                        "-ErrorAction SilentlyContinue | "
                        "Select-Object -ExpandProperty OwningProcess | "
                        "Sort-Object -Unique"
                    ),
                ],
                capture_output=True,
                text=True,
            )
            return [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]

        result = subprocess.run(
            ["fuser", f"{port}/tcp"],
            capture_output=True,
            text=True,
        )
        return [int(token) for token in result.stdout.split() if token.isdigit()]
    except Exception:
        return []


def _process_name(pid: int) -> str | None:
    """Return the process name for *pid* if it can be determined."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                [
                    "powershell",
                    "-NonInteractive",
                    "-Command",
                    f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName",
                ],
                capture_output=True,
                text=True,
            )
            name = result.stdout.strip()
            return name or None

        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
        )
        name = result.stdout.strip()
        return name or None
    except Exception:
        return None


def _has_kubectl_listener(port: int) -> bool:
    for pid in _listening_pids(port):
        name = _process_name(pid)
        if name and name.lower() == "kubectl":
            return True
    return False


def _port_is_accepting(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _kubectl_forward_is_healthy(port: int) -> bool:
    return _has_kubectl_listener(port) and _port_is_accepting(port)


def _kill_stale_port_forward(port: int) -> None:
    """Kill stale kubectl listeners on *port* so a new forward can bind.

    Only kubectl processes are killed; unrelated apps on the port are left
    in place (ported verbatim behavior from services/startup.py).
    """
    try:
        for pid in _listening_pids(port):
            if pid == 0:
                continue
            name = _process_name(pid)
            if not name or name.lower() != "kubectl":
                logger.info(
                    "k8s-launcher: leaving existing %s PID=%s on port %s in place",
                    name or "unknown-process",
                    pid,
                    port,
                )
                continue
            if platform.system() == "Windows":
                subprocess.run(
                    [
                        "powershell",
                        "-NonInteractive",
                        "-Command",
                        f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue",
                    ],
                    capture_output=True,
                )
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True)
            logger.info("k8s-launcher: killed stale kubectl PID=%s holding port %s", pid, port)
    except Exception as exc:
        logger.debug("k8s-launcher: _kill_stale_port_forward(%s) failed (non-fatal): %s", port, exc)


def _terminate_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


@dataclass
class PortForwardSpec:
    service: str          # platform service name (registry key)
    k8s_service: str      # kubernetes Service name
    namespace: str
    local_port: int
    target_port: int


# ── Service → Kubernetes Service name + target port ─────────────────────────
# Maps platform service names to (k8s_service_name, target_port_in_cluster).

DEFAULT_K8S_SERVICE_NAMES: dict[str, tuple[str, int]] = {
    "postgres":           ("compassx-postgres",           5432),
    "redis":              ("compassx-redis",              6379),
    "minio":              ("minio",                       9000),
    "minio-console":      ("minio-console",               9001),
    "airflow":            ("compassx-airflow",            8080),
    "enterprise-gateway": ("compassx-enterprise-gateway", 8888),
    "jupyter-server":     ("compassx-jupyter-server",     8889),
    "backend":            ("compassx-backend",            8000),
    "prometheus":         ("compassx-prometheus",         9090),
    # frontend: handled specially below (port-forward to ingress-nginx-controller)
}

# Platform service name → Kubernetes Deployment name (may differ from service name).
_DEPLOYMENT_NAMES: dict[str, str] = {
    "postgres":           "compassx-postgres",
    "redis":              "compassx-redis",
    "minio":              "minio",
    "airflow":            "compassx-airflow",
    "enterprise-gateway": "compassx-enterprise-gateway",
    "jupyter-server":     "compassx-jupyter-server",
    "backend":            "compassx-backend",
    "frontend":           "compassx-frontend",
    "prometheus":         "compassx-prometheus",
}


class KubernetesLauncher(Launcher):
    name = "kubernetes"

    def __init__(
        self,
        profile: DeploymentProfile,
        repo_root: Path,
        *,
        local_ports: dict[str, int] | None = None,
    ) -> None:
        self._profile = profile
        self._repo_root = repo_root
        self._backend_dir = repo_root / "backend"
        self._namespace = profile.k8s_namespace
        self._local_ports = local_ports or {}
        self._pf_processes: dict[str, subprocess.Popen] = {}
        self._pf_tasks: dict[str, asyncio.Task] = {}

    # ── low-level command execution with diagnostics ─────────────────────

    async def _run(self, cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> str:
        logger.info("k8s-launcher: running %s", " ".join(cmd))
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise LauncherError(self._diagnose(cmd, result.returncode, result.stderr or ""))
        return result.stdout

    @staticmethod
    def _diagnose(cmd: list[str], rc: int, stderr: str) -> str:
        lowered = stderr.lower()
        tool = cmd[0]
        if "connection refused" in lowered or "unable to connect to the server" in lowered:
            return (
                f"Cannot reach the Kubernetes API server. Is the cluster running? "
                f"For local dev run `minikube start`. ({tool} rc={rc}: {stderr.strip()})"
            )
        if "virtualalloc" in lowered or "out of memory" in lowered or "not enough memory" in lowered:
            return (
                "minikube/Docker Desktop ran out of memory while loading images. "
                "Increase Docker Desktop / WSL2 / minikube memory (e.g. 6-8 GiB) and retry. "
                f"Details: {stderr.strip()}"
            )
        if "not found" in lowered and tool == "minikube":
            return (
                f"minikube reported a missing resource. Details: {stderr.strip()}"
            )
        if "executable file not found" in lowered or "is not recognized" in lowered:
            return (
                f"'{tool}' is not installed or not on PATH. Install it and retry."
            )
        if "forbidden" in lowered or "unauthorized" in lowered:
            return (
                f"Kubernetes rejected the request (RBAC/auth). Check kubeconfig "
                f"context and permissions. Details: {stderr.strip()}"
            )
        return f"{' '.join(cmd)} failed (rc={rc}): {stderr.strip() or '<no stderr>'}"

    # ── images (ported from startup.py ensure_*_image) ───────────────────

    def _registry_prefix(self) -> str:
        return compute_settings.COMPUTE_REGISTRY_PREFIX.strip().rstrip("/")

    def _resolve_image(self, tag: str) -> str:
        prefix = self._registry_prefix()
        return f"{prefix}/{tag}" if prefix else tag

    async def _image_in_minikube(self, tag: str) -> bool:
        result = await asyncio.to_thread(
            subprocess.run, ["minikube", "image", "list"], capture_output=True, text=True
        )
        bare = tag.split("/")[-1]
        return any(bare in line for line in (result.stdout or "").splitlines())

    async def ensure_images(self) -> None:
        """Build/pull custom images and load into minikube (idempotent).

        Shows a step-based progress indicator with approximate timings because
        `minikube image load` does not expose fine-grained upload progress.
        """
        images = [
            # (load_ref, dockerfile, build_context, approx_minutes, pull_only, apply_registry_prefix, force_load, source_ref)
            ("compassx-enterprise-gateway:latest", "Dockerfile.eg", self._backend_dir, 2.5, False, True, False, None),
            ("compassx-backend-minikube:latest", "Dockerfile.minikube", self._backend_dir, 3.0, False, True, False, None),
            ("compassx-frontend:latest", "Dockerfile", self._repo_root / "frontend", 2.5, False, True, False, None),
            ("compassx-airflow-notebook-runner:latest", "Dockerfile.airflow-notebook", self._backend_dir, 2.0, False, True, False, None),
            ("compassx-compute-duckdb:latest", "Dockerfile.compute-duckdb", self._backend_dir, 1.5, False, True, False, None),
            ("compassx-jupyter-server:latest", "Dockerfile.jupyter-server", self._backend_dir, 1.5, False, True, False, None),
            ("compassx-ingress-nginx-controller:v1.14.3", None, self._backend_dir, 1.0, True, False, False, "registry.k8s.io/ingress-nginx/controller:v1.14.3"),
            ("apache/airflow:2.9.3-python3.11", None, self._backend_dir, 1.0, True, False, False, None),
        ]
        console = Console()
        total_est = sum(item[3] for item in images)
        console.print(f"[cyan]Preparing Kubernetes images[/cyan] (estimated {total_est:.1f} min total)")
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("{task.completed}/{task.total} steps"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            for tag, dockerfile, context_dir, approx_min, pull_only, apply_prefix, force_load, source_ref in images:
                resolved_tag = self._resolve_image(tag) if apply_prefix else tag
                task = progress.add_task(
                    f"{resolved_tag} [{approx_min:.1f} min est.]",
                    total=2,
                )
                if (not force_load) and await self._image_in_minikube(resolved_tag):
                    logger.info("k8s-launcher: image %s already in minikube, skip", resolved_tag)
                    progress.update(task, completed=2, description=f"{resolved_tag} [cached]")
                    continue
                if pull_only:
                    pull_target = source_ref or resolved_tag
                    logger.info("k8s-launcher: pulling %s", pull_target)
                    progress.update(task, advance=0, description=f"{resolved_tag} pulling...")
                    await self._run(["docker", "pull", pull_target], cwd=context_dir)
                    if source_ref and source_ref != resolved_tag:
                        await self._run(["docker", "tag", source_ref, resolved_tag], cwd=context_dir)
                else:
                    path = context_dir / dockerfile
                    if not path.exists():
                        raise LauncherError(f"Dockerfile not found: {path}")
                    logger.info("k8s-launcher: building %s from %s", resolved_tag, path)
                    progress.update(task, advance=0, description=f"{resolved_tag} building...")
                    build_cmd = ["docker", "build", "-f", dockerfile, "-t", resolved_tag, "."]
                    await self._run(build_cmd, cwd=context_dir)
                logger.info("k8s-launcher: loading %s into minikube", resolved_tag)
                progress.update(task, advance=1, description=f"{resolved_tag} loading into minikube...")
                await self._run(["minikube", "image", "load", resolved_tag])
                progress.update(task, advance=1, description=f"{resolved_tag} done")

    # ── RBAC (delegates to existing idempotent implementation) ───────────

    async def ensure_rbac(self) -> None:
        """ServiceAccount + ClusterRole + binding so EG can exec into pods."""
        await asyncio.to_thread(self._ensure_rbac_sync)

    def _ensure_rbac_sync(self) -> None:
        from compassx.drivers.k8s_client import K8sApiClient
        from kubernetes import client as k8s_client
        from kubernetes.client.exceptions import ApiException
        from services.enterprise_gateway.config import eg_settings

        k8s = K8sApiClient()
        eg_ns = eg_settings.EG_NAMESPACE
        kernel_ns = eg_settings.KERNEL_NAMESPACE
        sa_name = "compassx-eg"
        cr_name = "compassx-eg"

        for ns in {eg_ns, kernel_ns}:
            try:
                k8s.core().read_namespace(name=ns)
            except ApiException as exc:
                if exc.status == 404:
                    k8s.core().create_namespace(
                        body=k8s_client.V1Namespace(
                            metadata=k8s_client.V1ObjectMeta(name=ns, labels={"compassx/managed": "true"})
                        )
                    )
                else:
                    raise

        try:
            k8s.core().read_namespaced_service_account(name=sa_name, namespace=eg_ns)
        except ApiException as exc:
            if exc.status == 404:
                k8s.core().create_namespaced_service_account(
                    namespace=eg_ns,
                    body=k8s_client.V1ServiceAccount(
                        metadata=k8s_client.V1ObjectMeta(name=sa_name, namespace=eg_ns, labels={"app": "compassx"})
                    ),
                )

        rules = [
            k8s_client.V1PolicyRule(api_groups=[""], resources=["pods"], verbs=["get", "list", "watch"]),
            k8s_client.V1PolicyRule(api_groups=[""], resources=["pods/exec"], verbs=["create", "get"]),
            k8s_client.V1PolicyRule(api_groups=[""], resources=["pods/log"], verbs=["get"]),
            k8s_client.V1PolicyRule(api_groups=[""], resources=["namespaces"], verbs=["get", "list"]),
        ]
        cr_body = k8s_client.V1ClusterRole(
            metadata=k8s_client.V1ObjectMeta(name=cr_name, labels={"app": "compassx"}),
            rules=rules,
        )
        try:
            k8s.rbac().replace_cluster_role(name=cr_name, body=cr_body)
        except ApiException as exc:
            if exc.status == 404:
                k8s.rbac().create_cluster_role(body=cr_body)
            else:
                raise

        crb_body = k8s_client.V1ClusterRoleBinding(
            metadata=k8s_client.V1ObjectMeta(name=cr_name, labels={"app": "compassx"}),
            subjects=[k8s_client.RbacV1Subject(kind="ServiceAccount", name=sa_name, namespace=eg_ns)],
            role_ref=k8s_client.V1RoleRef(api_group="rbac.authorization.k8s.io", kind="ClusterRole", name=cr_name),
        )
        try:
            k8s.rbac().replace_cluster_role_binding(name=cr_name, body=crb_body)
        except ApiException as exc:
            if exc.status == 404:
                k8s.rbac().create_cluster_role_binding(body=crb_body)
            else:
                raise
        logger.info("k8s-launcher: RBAC ready")

    # ── port-forwards (generic supervised loop) ──────────────────────────

    def _port_forward_specs(self, services: list[str]) -> list[PortForwardSpec]:
        """Build port-forward specs for the given service names.

        The frontend is a special case in kubernetes-local: instead of
        forwarding to the frontend pod directly, we forward to the
        ingress-nginx-controller so all traffic goes through ingress routing.
        """
        specs = []
        for service in services:
            if service == "frontend" and self._profile.name == "kubernetes-local":
                # Forward localhost:18080 -> ingress-nginx-controller:80
                # This gives the same URL structure as production.
                specs.append(
                    PortForwardSpec(
                        service=service,
                        k8s_service="ingress-nginx-controller",
                        namespace="ingress-nginx",
                        local_port=self._local_ports.get(service, 18080),
                        target_port=80,
                    )
                )
                continue
            entry = DEFAULT_K8S_SERVICE_NAMES.get(service)
            if entry is None:
                continue
            k8s_name, target_port = entry
            local_port = self._local_ports.get(service, target_port)
            specs.append(
                PortForwardSpec(
                    service=service,
                    k8s_service=k8s_name,
                    namespace=self._namespace,
                    local_port=local_port,
                    target_port=target_port,
                )
            )
        return specs

    async def _wait_for_k8s_service(self, namespace: str, name: str, timeout: float = 300.0) -> None:
        """Poll until the K8s Service exists (created by kubectl apply)."""
        import time
        deadline = time.monotonic() + timeout
        while True:
            result = await asyncio.to_thread(
                subprocess.run,
                ["kubectl", "get", "svc", name, "-n", namespace, "-o", "name"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return
            if time.monotonic() > deadline:
                logger.warning(
                    "k8s-launcher: service %s/%s not found after %.0fs, starting port-forward anyway",
                    namespace, name, timeout,
                )
                return
            logger.debug(
                "k8s-launcher: waiting for service %s/%s to be created...", namespace, name
            )
            await asyncio.sleep(10)

    async def _port_forward_loop(self, spec: PortForwardSpec) -> None:
        """Supervised kubectl port-forward: health-checked, auto-restarted.

        Generic version of the six duplicated loops in services/startup.py.
        """
        label = spec.service
        logger.info(
            "%s [%s] status=WAITING_SERVICE | waiting for service %s/%s",
            _PF_LOG_PREFIX, label, spec.namespace, spec.k8s_service,
        )
        await self._wait_for_k8s_service(spec.namespace, spec.k8s_service)
        await asyncio.to_thread(_kill_stale_port_forward, spec.local_port)

        while True:
            try:
                if await asyncio.to_thread(_kubectl_forward_is_healthy, spec.local_port):
                    await asyncio.sleep(10)
                    continue
                if await asyncio.to_thread(_has_kubectl_listener, spec.local_port):
                    logger.warning(
                        "%s [%s] status=BROKEN | localhost:%s has kubectl listener but not accepting; restarting",
                        _PF_LOG_PREFIX, label, spec.local_port,
                    )
                    await asyncio.to_thread(_kill_stale_port_forward, spec.local_port)
                await asyncio.to_thread(_terminate_process, self._pf_processes.get(label))
                logger.info(
                    "%s [%s] status=STARTING | kubectl port-forward svc/%s %s:%s -n %s",
                    _PF_LOG_PREFIX, label, spec.k8s_service, spec.local_port,
                    spec.target_port, spec.namespace,
                )
                # Plain subprocess: Windows uvicorn runs a selector loop that
                # cannot spawn asyncio subprocesses.
                proc = subprocess.Popen(
                    [
                        "kubectl", "port-forward",
                        f"svc/{spec.k8s_service}",
                        f"{spec.local_port}:{spec.target_port}",
                        "-n", spec.namespace,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                self._pf_processes[label] = proc
                rc = await asyncio.to_thread(proc.wait)
                stderr = b""
                if proc.stderr is not None:
                    stderr = await asyncio.to_thread(proc.stderr.read)
                err = stderr.decode(errors="replace").strip()
                logger.warning(
                    "%s [%s] status=EXITED | rc=%s%s; restarting in 1s",
                    _PF_LOG_PREFIX, label, rc, f" stderr={err}" if err else "",
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - supervised loop
                logger.warning(
                    "%s [%s] status=ERROR | %s; retrying in 1s", _PF_LOG_PREFIX, label, exc
                )
            finally:
                self._pf_processes.pop(label, None)
            await asyncio.sleep(1)

    def start_port_forwards(self, services: list[str]) -> None:
        loop = asyncio.get_event_loop()
        for spec in self._port_forward_specs(services):
            task = self._pf_tasks.get(spec.service)
            if task is None or task.done():
                self._pf_tasks[spec.service] = loop.create_task(
                    self._port_forward_loop(spec)
                )
                logger.info(
                    "k8s-launcher: port-forward task scheduled: localhost:%s -> %s/%s:%s",
                    spec.local_port, spec.namespace, spec.k8s_service, spec.target_port,
                )

    def stop_port_forwards(self) -> None:
        for task in self._pf_tasks.values():
            task.cancel()
        self._pf_tasks.clear()
        for proc in self._pf_processes.values():
            _terminate_process(proc)
        self._pf_processes.clear()

    # ── manifest application helpers ─────────────────────────────────────

    def _render_manifest_text(self, source: Path, replacements: dict[str, str]) -> str:
        text = source.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _write_temp_manifest(self, text: str) -> Path:
        import tempfile
        fd, path = tempfile.mkstemp(prefix="compassx-k8s-", suffix=".yaml")
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        return Path(path)

    async def _apply_manifests(self, files: list[Path]) -> None:
        """Apply all existing manifests in a single kubectl apply call."""
        existing = [p for p in files if p.exists()]
        missing = [p for p in files if not p.exists()]
        if missing:
            for p in missing:
                logger.warning("k8s-launcher: manifest not found (skipped): %s", p)
        if not existing:
            logger.warning("k8s-launcher: no manifests to apply")
            return
        cmd = ["kubectl", "apply", "-f", str(existing[0])]
        for p in existing[1:]:
            cmd.extend(["-f", str(p)])
        await self._run(cmd)

    async def _apply_local_ingress_controller(self) -> None:
        """Apply ingress-nginx idempotently using --server-side strategy.

        Uses server-side apply so re-running `compassx up` does NOT tear
        down the ingress controller (avoiding downtime on repeated runs).
        """
        if self._profile.name != "kubernetes-local":
            return
        manifest = self._repo_root / "k8s" / "ingress-nginx-local.yaml"
        if not manifest.exists():
            raise LauncherError(f"Local ingress controller manifest not found: {manifest}")

        logger.info("k8s-launcher: applying ingress-nginx controller (server-side apply)")
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "kubectl", "apply",
                "--server-side",
                "--force-conflicts",
                "-f", str(manifest),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Fall back to regular apply if server-side isn't supported
            logger.warning(
                "k8s-launcher: server-side apply failed (rc=%s), retrying with standard apply: %s",
                result.returncode, (result.stderr or "").strip()
            )
            result2 = await asyncio.to_thread(
                subprocess.run,
                ["kubectl", "apply", "-f", str(manifest)],
                capture_output=True,
                text=True,
            )
            if result2.returncode != 0:
                raise LauncherError(
                    self._diagnose(
                        ["kubectl", "apply", "-f", str(manifest)],
                        result2.returncode,
                        result2.stderr or result2.stdout or "",
                    )
                )
        logger.info("k8s-launcher: ingress-nginx controller applied successfully")

    async def _ensure_kernelspecs_configmap(self) -> None:
        try:
            from kubernetes.client.exceptions import ApiException
            from compassx.drivers.k8s_client import K8sApiClient
            from services.enterprise_gateway.kernelspecs import build_kernelspec_configmap
        except ImportError as exc:
            logger.warning(
                "k8s-launcher: cannot import kernelspecs module (non-fatal): %s. "
                "Kernelspec ConfigMap will not be updated — "
                "ensure compassx-kernelspecs ConfigMap is created manually if needed.",
                exc,
            )
            return

        cm = build_kernelspec_configmap(
            self._namespace,
            catalog_api_url=(
                f"http://compassx-backend.{self._namespace}.svc.cluster.local:8000/api/v1/catalog"
            ),
        )
        k8s = K8sApiClient()
        core = k8s.core()
        try:
            core.replace_namespaced_config_map(
                name=cm.metadata.name, namespace=self._namespace, body=cm
            )
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespaced_config_map(namespace=self._namespace, body=cm)
            else:
                raise

    # ── .env → K8s Secret for external services ──────────────────────────

    # Keys to extract from .env per external service.
    # Values are injected into the compassx-backend-secrets Secret so the
    # backend pod can connect to the user's service without code changes.
    _ENV_KEYS_BY_SERVICE: dict[str, list[str]] = {
        "postgres": [
            "PG_HOST", "PG_PORT", "PG_USER", "PG_PASSWORD",
            # Airflow also uses postgres — pick up its override if present
            "AIRFLOW_PG_HOST", "AIRFLOW_PG_PORT",
            "AIRFLOW_PG_USER", "AIRFLOW_PG_PASSWORD", "AIRFLOW_PG_DATABASE",
        ],
        "redis": [
            "REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD",
        ],
        "minio": [
            "MINIO_INTERNAL_ENDPOINT", "MINIO_EXTERNAL_ENDPOINT",
            "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
            "MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD",
            "COMPASSX_MINIO_ROOT_USER", "COMPASSX_MINIO_ROOT_PASSWORD",
        ],
        "airflow": [
            "AIRFLOW_API_BASE_URL", "AIRFLOW_BACKEND_API_URL",
            "AIRFLOW_WEBSERVER_URL", "AIRFLOW_UI_URL",
        ],
    }

    # Env-var keys whose *values* contain hostnames that need localhost→minikube rewrite.
    # Only plain host keys are listed; URL keys are handled with string replacement.
    _HOST_KEYS: frozenset[str] = frozenset({
        "PG_HOST", "AIRFLOW_PG_HOST", "REDIS_HOST",
    })
    _URL_KEYS: frozenset[str] = frozenset({
        "REDIS_URL",
        "MINIO_INTERNAL_ENDPOINT", "MINIO_EXTERNAL_ENDPOINT",
        "AIRFLOW_API_BASE_URL", "AIRFLOW_BACKEND_API_URL",
        "AIRFLOW_WEBSERVER_URL", "AIRFLOW_UI_URL",
    })

    @staticmethod
    def _parse_dotenv(path: Path) -> dict[str, str]:
        """Parse a .env file into a {key: value} dict.

        Handles:
        - KEY=VALUE and KEY="VALUE" and KEY='VALUE'
        - Inline # comments
        - Blank lines and # comment lines
        - No variable expansion (values are returned literally)
        """
        result: dict[str, str] = {}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return result
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, raw_val = line.partition("=")
            key = key.strip()
            val = raw_val.strip()
            # Strip surrounding quotes
            if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]
            # Strip trailing inline comment (only outside quotes)
            else:
                val = val.split("#")[0].strip()
            result[key] = val
        return result

    @staticmethod
    def _rewrite_localhost(value: str, is_url: bool, gateway: str) -> str:
        """Replace localhost/127.0.0.1 with host.minikube.internal in host or URL values.

        Pods inside minikube cannot reach the host's localhost — they must use
        host.minikube.internal (or the gateway IP) to connect to host-resident services.
        """
        for local in ("localhost", "127.0.0.1"):
            if is_url:
                # Replace in full URL: http://localhost:5432 → http://host.minikube.internal:5432
                value = value.replace(f"://{local}", f"://{gateway}")
                value = value.replace(f"://{local}:", f"://{gateway}:")
            else:
                if value.strip() in (local, ""):
                    value = gateway
        return value

    def _find_dotenv(self) -> Path | None:
        """Locate .env — checks backend/ first, then repo root."""
        for candidate in (
            self._backend_dir / ".env",
            self._repo_root / ".env",
        ):
            if candidate.exists():
                logger.debug("k8s-launcher: found .env at %s", candidate)
                return candidate
        return None

    async def _sync_external_secrets_from_env(
        self, external_services: list[str]
    ) -> None:
        """Read .env and push relevant keys to compassx-backend-secrets Secret.

        For each external service, the matching env-var keys are read from the
        user's .env file. Localhost addresses are rewritten to
        host.minikube.internal so backend pods can reach host-resident services.

        The Secret is created if absent or updated (replaced) if it already exists,
        making the operation idempotent.
        """
        env_path = self._find_dotenv()
        if env_path is None:
            logger.warning(
                "k8s-launcher: external_services=%s but no .env file found "
                "(checked %s and %s). "
                "Create compassx-backend-secrets Secret manually — "
                "see k8s/secrets/README.md",
                external_services,
                self._backend_dir / ".env",
                self._repo_root / ".env",
            )
            return

        dotenv = self._parse_dotenv(env_path)
        logger.info("k8s-launcher: read %d keys from %s", len(dotenv), env_path)

        gateway = os.environ.get("COMPASSX_HOST_GATEWAY", "host.minikube.internal")
        secret_data: dict[str, str] = {}

        for service in external_services:
            keys = self._ENV_KEYS_BY_SERVICE.get(service)
            if keys is None:
                logger.debug(
                    "k8s-launcher: no .env key mapping for external service '%s' — "
                    "add connection details to compassx-backend-secrets manually",
                    service,
                )
                continue

            found = 0
            for key in keys:
                value = dotenv.get(key)
                if value is None:
                    continue
                # Rewrite localhost → host.minikube.internal
                if key in self._HOST_KEYS:
                    value = self._rewrite_localhost(value, is_url=False, gateway=gateway)
                elif key in self._URL_KEYS:
                    value = self._rewrite_localhost(value, is_url=True, gateway=gateway)
                secret_data[key] = value
                found += 1

            if found:
                logger.info(
                    "k8s-launcher: [%s] loaded %d key(s) from .env "
                    "(localhost → %s rewrite applied)",
                    service, found, gateway,
                )
            else:
                logger.warning(
                    "k8s-launcher: [%s] no matching keys found in .env "
                    "(expected one of: %s)",
                    service, ", ".join(keys),
                )

        if not secret_data:
            logger.warning(
                "k8s-launcher: external_services=%s — no keys found in .env, "
                "compassx-backend-secrets will not be created. "
                "See k8s/secrets/README.md",
                external_services,
            )
            return

        # Upsert the Secret
        try:
            from kubernetes import client as k8s_client
            from kubernetes.client.exceptions import ApiException
            from compassx.drivers.k8s_client import K8sApiClient
        except ImportError as exc:
            logger.warning(
                "k8s-launcher: cannot create external-services Secret "
                "(kubernetes package not available): %s", exc
            )
            return

        secret_body = k8s_client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=k8s_client.V1ObjectMeta(
                name="compassx-backend-secrets",
                namespace=self._namespace,
                labels={
                    "app": "compassx",
                    "compassx/managed": "true",
                    "compassx/source": "dotenv",
                },
            ),
            type="Opaque",
            string_data=secret_data,
        )
        k8s = K8sApiClient()
        core = k8s.core()
        try:
            core.replace_namespaced_secret(
                name="compassx-backend-secrets",
                namespace=self._namespace,
                body=secret_body,
            )
            logger.info(
                "k8s-launcher: updated compassx-backend-secrets (%d key(s)): %s",
                len(secret_data),
                ", ".join(sorted(secret_data)),
            )
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespaced_secret(
                    namespace=self._namespace,
                    body=secret_body,
                )
                logger.info(
                    "k8s-launcher: created compassx-backend-secrets (%d key(s)): %s",
                    len(secret_data),
                    ", ".join(sorted(secret_data)),
                )
            else:
                raise

    # ── Launcher interface ───────────────────────────────────────────────

    async def start(self, services: list[str]) -> None:
        """Deploy platform services to Kubernetes.

        kubernetes-local flow:
        1. (Optional) ensure_images  — build and load custom images into minikube
        2. (Optional) ensure_rbac    — create SA/ClusterRole/ClusterRoleBinding
        3. Apply ingress-nginx       — idempotent via server-side apply
        4. Apply all K8s manifests   — namespace, RBAC, infra, app services
        5. (Optional) port-forwards  — supervised kubectl port-forward loops
        """
        if self._profile.k8s_ensure_images:
            await self.ensure_images()
        if self._profile.k8s_ensure_rbac:
            await self.ensure_rbac()

        # ── Sync external-service connection details from .env → K8s Secret ──
        # Must run before manifests are applied so the Secret exists when the
        # backend Deployment starts (avoids env-var injection race on first run).
        if self._profile.k8s_external_services:
            await self._sync_external_secrets_from_env(
                self._profile.k8s_external_services
            )

        manifests = self._repo_root / "k8s"
        if not manifests.exists():
            logger.warning("k8s-launcher: manifests directory not found: %s", manifests)
            return

        temp_files: list[Path] = []

        if self._profile.name == "kubernetes-local":
            # ── Apply ingress-nginx (idempotent, separate from main manifests) ──
            await self._apply_local_ingress_controller()

            # ── Build kernelspecs ConfigMap ────────────────────────────────────
            await self._ensure_kernelspecs_configmap()

            # ── Render image-patched manifests for local minikube images ───────
            backend_dep  = manifests / "backend-runtime.yaml"
            frontend_dep = manifests / "frontend-deployment.yaml"
            eg_dep       = manifests / "services" / "enterprise-gateway" / "deployment.yaml"
            js_dep       = manifests / "services" / "jupyter-server" / "deployment.yaml"

            render_map = {
                "imagePullPolicy: Always":    "imagePullPolicy: IfNotPresent",
                "compassx-backend-minikube:latest":   self._resolve_image("compassx-backend-minikube:latest"),
                "compassx-frontend:latest":           self._resolve_image("compassx-frontend:latest"),
                "acrecgci.azurecr.io/compassx-enterprise-gateway:latest": self._resolve_image("compassx-enterprise-gateway:latest"),
                "quay.io/jupyter/base-notebook:latest": self._resolve_image("compassx-jupyter-server:latest"),
            }

            for src in (backend_dep, frontend_dep, eg_dep, js_dep):
                if src.exists():
                    temp_files.append(self._write_temp_manifest(self._render_manifest_text(src, render_map)))
                else:
                    logger.warning("k8s-launcher: manifest not found (skipped): %s", src)

            # ── Full ordered manifest list for kubernetes-local ──────────────
            # Infrastructure first (databases, object-store) → platform services
            #
            # Services listed in k8s_external_services are skipped here —
            # their infrastructure is owned by the user (RDS, managed Redis, etc.)
            # Connection details come from the compassx-backend-secrets Secret.
            external = set(self._profile.k8s_external_services)
            if external:
                logger.info(
                    "k8s-launcher: external services (manifests skipped): %s",
                    ", ".join(sorted(external)),
                )

            # Map: platform service name → its infrastructure manifest path.
            # Only infrastructure services that can be brought externally are listed;
            # platform services (backend, frontend, EG, jupyter) are always deployed.
            _infra_manifests: dict[str, Path] = {
                "postgres":   manifests / "services" / "postgres"   / "postgres.yaml",
                "redis":      manifests / "services" / "redis"      / "redis.yaml",
                "minio":      manifests / "services" / "minio"      / "minio.yaml",
                "airflow":    manifests / "services" / "airflow"    / "airflow.yaml",
                "prometheus": manifests / "services" / "prometheus" / "prometheus.yaml",
            }

            infra_files = [
                path for svc, path in _infra_manifests.items()
                if svc not in external
            ]

            apply_files = [
                # Cluster structure
                manifests / "namespace.yaml",
                manifests / "rbac.yaml",
                manifests / "rbac" / "eg-rbac.yaml",
                # App configuration
                manifests / "app-config-local.yaml",
                # Infrastructure services (external ones are skipped above)
                *infra_files,
                # Frontend nginx config + services
                manifests / "frontend-nginx-config.yaml",
                manifests / "frontend-service.yaml",
                # Backend + frontend deployments (patched for local images)
                *temp_files,
                # Backend service
                manifests / "backend-service.yaml",
                # EG + Jupyter services
                manifests / "services" / "enterprise-gateway" / "service.yaml",
                manifests / "services" / "jupyter-server"     / "service.yaml",
                # Ingress rule (routes /api → backend, / → frontend)
                manifests / "ingress.yaml",
            ]
        else:
            # Cloud / managed Kubernetes: use manifests as-is (no image patching).
            apply_files = [
                manifests / "namespace.yaml",
                manifests / "app-config.yaml",
                manifests / "rbac.yaml",
                manifests / "rbac" / "eg-rbac.yaml",
                manifests / "frontend-nginx-config.yaml",
                manifests / "ingress.yaml",
                manifests / "backend-deployment.yaml",
                manifests / "backend-service.yaml",
                manifests / "frontend-deployment.yaml",
                manifests / "frontend-service.yaml",
                manifests / "services" / "enterprise-gateway" / "deployment.yaml",
                manifests / "services" / "enterprise-gateway" / "service.yaml",
                manifests / "services" / "jupyter-server" / "deployment.yaml",
                manifests / "services" / "jupyter-server" / "service.yaml",
            ]

        await self._apply_manifests(apply_files)

        # Clean up temp files after apply
        for tf in temp_files:
            try:
                tf.unlink()
            except Exception:
                pass

        if self._profile.k8s_port_forwards:
            # Only forward services the developer needs to reach from the host.
            # All cluster-internal traffic goes through DNS — no port-forwards needed
            # between services in the cluster.
            exposed = self._profile.k8s_exposed_services or ["frontend"]
            self.start_port_forwards(exposed)
            logger.info(
                "k8s-launcher: port-forwards active for: %s",
                ", ".join(exposed),
            )

        logger.info("k8s-launcher: services started: %s", ", ".join(services))

    async def stop(self, services: list[str]) -> None:
        """Scale platform workloads to zero (preserves resources, fast restart)."""
        self.stop_port_forwards()
        for service in services:
            workload = _DEPLOYMENT_NAMES.get(service)
            if workload is None:
                continue
            # Try scaling deployment first, then statefulset
            for kind in ("deployment", "statefulset"):
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "kubectl", "scale", kind, workload,
                        "--replicas=0", "-n", self._namespace,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    break

    async def restart(self, services: list[str]) -> None:
        for service in services:
            workload = _DEPLOYMENT_NAMES.get(service)
            if workload is None:
                continue
            for kind in ("deployment", "statefulset"):
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "kubectl", "rollout", "restart", f"{kind}/{workload}",
                        "-n", self._namespace,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    break

    async def status(self, services: list[str]) -> LauncherStatus:
        statuses = []
        for service in services:
            workload = _DEPLOYMENT_NAMES.get(service)
            if workload is None:
                statuses.append(
                    ServiceStatus(name=service, running=False, detail="no k8s mapping")
                )
                continue

            ready_str = ""
            for kind in ("deployment", "statefulset"):
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "kubectl", "get", kind, workload, "-n", self._namespace,
                        "-o", "jsonpath={.status.readyReplicas}/{.status.replicas}",
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    ready_str = result.stdout.strip()
                    break

            if not ready_str:
                statuses.append(
                    ServiceStatus(name=service, running=False, detail="not deployed")
                )
                continue

            ready, _, total = ready_str.partition("/")
            running = bool(ready and ready != "0" and ready == total)
            statuses.append(
                ServiceStatus(
                    name=service,
                    running=running,
                    healthy=running or None,
                    detail=f"replicas {ready_str}",
                )
            )
        return LauncherStatus(launcher=self.name, services=statuses)

    async def logs(self, service: str, tail: int = 200) -> str:
        workload = _DEPLOYMENT_NAMES.get(service)
        if workload is None:
            raise LauncherError(f"No Kubernetes mapping for service '{service}'")
        for kind in ("deployment", "statefulset"):
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "kubectl", "logs", f"{kind}/{workload}",
                    "-n", self._namespace, "--tail", str(tail),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout
        raise LauncherError(f"Could not fetch logs for service '{service}'")
