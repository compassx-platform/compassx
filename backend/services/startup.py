"""CompassX startup automation.

Runs automatically when FastAPI starts (via lifespan).  Covers:

1. RBAC — ServiceAccount + ClusterRole + bindings so EG pod can exec into
   compute pods and list pods.
2. EG image — builds compassx-enterprise-gateway:latest from Dockerfile.eg and
   loads it into minikube if not already present.
3. Jupyter Server port-forward — keeps a kubectl port-forward running in the
   background (8889 → Jupyter Server) so the browser can reach it.  The
   forward is restarted automatically if it dies.
"""
import asyncio
import logging
import platform
import socket
import subprocess
from pathlib import Path

from kubernetes import client as k8s_client
from kubernetes.client.exceptions import ApiException
from compute.config import compute_settings
from services.backend_runtime import BACKEND_LOCAL_PORT, BACKEND_NAMESPACE, BACKEND_PORT, BACKEND_SERVICE_NAME, backend_service_url, clear_backend_port_forward_ready, get_backend_runtime_manager, mark_backend_port_forward_ready
from compute.k8s_client import get_k8s_client
from services.airflow.config import airflow_settings
from services.enterprise_gateway.config import eg_settings
from services.minio.config import minio_settings

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_SA_NAME = "compassx-eg"
_CLUSTER_ROLE_NAME = "compassx-eg"
_EG_NAMESPACE = eg_settings.EG_NAMESPACE
_KERNEL_NAMESPACE = eg_settings.KERNEL_NAMESPACE
_CUSTOM_IMAGE_TAG = "compassx-enterprise-gateway:latest"
_AIRFLOW_NOTEBOOK_IMAGE_TAG = "compassx-airflow-notebook-runner:latest"
_DOCKERFILE = Path(__file__).parent.parent / "Dockerfile.eg"
_AIRFLOW_NOTEBOOK_DOCKERFILE = Path(__file__).parent.parent / "Dockerfile.airflow-notebook"
_BACKEND_DIR = Path(__file__).parent.parent
_JS_SERVICE_NAME = "compassx-jupyter-server"
_JS_LOCAL_PORT = eg_settings.JUPYTER_SERVER_PORT

_EG_SERVICE_NAME = "compassx-enterprise-gateway"
_EG_LOCAL_PORT = eg_settings.EG_PORT
_AIRFLOW_SERVICE_NAME = airflow_settings.AIRFLOW_SERVICE_NAME
_AIRFLOW_LOCAL_PORT = airflow_settings.AIRFLOW_PORT
_MINIO_SERVICE_NAME = minio_settings.MINIO_SERVICE_NAME
_MINIO_LOCAL_PORT = minio_settings.MINIO_PORT
_MINIO_CONSOLE_SERVICE_NAME = minio_settings.MINIO_CONSOLE_SERVICE_NAME
_MINIO_CONSOLE_LOCAL_PORT = minio_settings.MINIO_CONSOLE_PORT
_PF_LOG_PREFIX = ">>> PORT-FORWARD <<<"

_pf_process: subprocess.Popen | None = None
_pf_task: asyncio.Task | None = None
_eg_pf_process: subprocess.Popen | None = None
_eg_pf_task: asyncio.Task | None = None
_airflow_pf_process: subprocess.Popen | None = None
_airflow_pf_task: asyncio.Task | None = None
_minio_pf_process: subprocess.Popen | None = None
_minio_pf_task: asyncio.Task | None = None
_minio_console_pf_process: subprocess.Popen | None = None
_minio_console_pf_task: asyncio.Task | None = None
_backend_pf_process: subprocess.Popen | None = None
_backend_pf_task: asyncio.Task | None = None
_minio_tunnel_process: subprocess.Popen | None = None
_minio_tunnel_task: asyncio.Task | None = None


def _pf_log(level: str, service: str, status: str, message: str, *args) -> None:
    """Log port-forward state with a high-visibility searchable prefix."""
    log = getattr(logger, level)
    full_message = message % args if args else message
    log("%s [%s] status=%s | %s", _PF_LOG_PREFIX, service, status, full_message)


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
    """Return True if a kubectl process is already listening on *port*."""
    for pid in _listening_pids(port):
        name = _process_name(pid)
        if name and name.lower() == "kubectl":
            return True
    return False


def _port_is_accepting(port: int) -> bool:
    """Return True if localhost accepts TCP connections on *port*."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _kubectl_forward_is_healthy(port: int) -> bool:
    """Return True if a kubectl listener exists and accepts connections."""
    return _has_kubectl_listener(port) and _port_is_accepting(port)


def _port_forward_specs() -> list[dict]:
    specs = [
        {
            "id": "jupyter-server",
            "label": "Jupyter Server",
            "namespace": _EG_NAMESPACE,
            "service_name": _JS_SERVICE_NAME,
            "local_port": _JS_LOCAL_PORT,
            "target_port": 8888,
            "mode": "port-forward",
            "task": _pf_task,
            "process": _pf_process,
        },
        {
            "id": "enterprise-gateway",
            "label": "Enterprise Gateway",
            "namespace": _EG_NAMESPACE,
            "service_name": _EG_SERVICE_NAME,
            "local_port": _EG_LOCAL_PORT,
            "target_port": _EG_LOCAL_PORT,
            "mode": "port-forward",
            "task": _eg_pf_task,
            "process": _eg_pf_process,
        },
        {
            "id": "airflow",
            "label": "Airflow",
            "namespace": airflow_settings.AIRFLOW_NAMESPACE,
            "service_name": _AIRFLOW_SERVICE_NAME,
            "local_port": _AIRFLOW_LOCAL_PORT,
            "target_port": _AIRFLOW_LOCAL_PORT,
            "mode": "port-forward",
            "task": _airflow_pf_task,
            "process": _airflow_pf_process,
        },
        {
            "id": "minio-api",
            "label": "MinIO API",
            "namespace": minio_settings.MINIO_NAMESPACE,
            "service_name": _MINIO_SERVICE_NAME,
            "local_port": _MINIO_LOCAL_PORT,
            "target_port": _MINIO_LOCAL_PORT,
            "mode": "port-forward",
            "task": _minio_pf_task,
            "process": _minio_pf_process,
        },
    ]
    if minio_settings.MINIO_LOCAL_ACCESS_MODE.lower() == "tunnel":
        specs.append(
            {
                "id": "minio-tunnel",
                "label": "MinIO Tunnel",
                "namespace": minio_settings.MINIO_NAMESPACE,
                "service_name": _MINIO_CONSOLE_SERVICE_NAME,
                "local_port": None,
                "target_port": None,
                "mode": "tunnel",
                "task": _minio_tunnel_task,
                "process": _minio_tunnel_process,
            }
        )
    else:
        specs.append(
            {
                "id": "minio-console",
                "label": "MinIO Console",
                "namespace": minio_settings.MINIO_NAMESPACE,
                "service_name": _MINIO_CONSOLE_SERVICE_NAME,
                "local_port": _MINIO_CONSOLE_LOCAL_PORT,
                "target_port": minio_settings.MINIO_CONSOLE_PORT,
                "mode": "port-forward",
                "task": _minio_console_pf_task,
                "process": _minio_console_pf_process,
            }
        )
    return specs


def get_port_forward_status() -> dict:
    """Return current localhost port-forward health for the Compute Services UI."""
    forwards = []
    for spec in _port_forward_specs():
        task = spec["task"]
        process = spec["process"]
        local_port = spec["local_port"]
        listener = bool(local_port and _has_kubectl_listener(local_port))
        accepting = bool(local_port and _port_is_accepting(local_port))
        task_running = bool(task and not task.done())
        process_running = bool(process and process.poll() is None)
        if spec["mode"] == "tunnel":
            state = "running" if process_running else "stopped"
            healthy = process_running
        elif listener and accepting:
            state = "healthy"
            healthy = True
        elif listener:
            state = "broken"
            healthy = False
        elif task_running:
            state = "waiting"
            healthy = False
        else:
            state = "stopped"
            healthy = False
        forwards.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "namespace": spec["namespace"],
                "service_name": spec["service_name"],
                "local_port": local_port,
                "target_port": spec["target_port"],
                "mode": spec["mode"],
                "state": state,
                "healthy": healthy,
                "listener": listener,
                "accepting": accepting,
                "task_running": task_running,
                "process_running": process_running,
                "pid": process.pid if process else None,
            }
        )
    return {
        "enabled": any(item["task_running"] or item["process_running"] for item in forwards),
        "healthy": all(item["healthy"] for item in forwards),
        "forwards": forwards,
    }


def _kill_stale_port_forward(port: int) -> None:
    """Kill stale kubectl listeners on *port* so our new forward can bind.

    On Windows, uses `netstat -ano` + `taskkill`.  On Linux/macOS, uses `fuser`.
    Errors are silently ignored. We intentionally avoid killing unrelated apps
    that happen to use the same local port.
    """
    try:
        for pid in _listening_pids(port):
            if pid == 0:
                continue
            name = _process_name(pid)
            if not name or name.lower() != "kubectl":
                logger.info(
                    "startup: leaving existing %s PID=%s on port %s in place",
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
            logger.info("startup: killed stale kubectl PID=%s holding port %s", pid, port)
    except Exception as exc:
        logger.debug("startup: _kill_stale_port_forward(%s) failed (non-fatal): %s", port, exc)


# ── RBAC ─────────────────────────────────────────────────────────────────────

def _ensure_namespace(name: str) -> None:
    k8s = get_k8s_client()
    try:
        k8s.core().read_namespace(name=name)
    except ApiException as exc:
        if exc.status == 404:
            ns = k8s_client.V1Namespace(
                metadata=k8s_client.V1ObjectMeta(
                    name=name,
                    labels={"compassx/managed": "true"},
                )
            )
            k8s.core().create_namespace(body=ns)
            logger.info("startup: created namespace %s", name)
        else:
            raise


def _ensure_service_account() -> None:
    k8s = get_k8s_client()
    try:
        k8s.core().read_namespaced_service_account(
            name=_SA_NAME, namespace=_EG_NAMESPACE
        )
        logger.debug("startup: ServiceAccount %s exists", _SA_NAME)
    except ApiException as exc:
        if exc.status == 404:
            sa = k8s_client.V1ServiceAccount(
                metadata=k8s_client.V1ObjectMeta(
                    name=_SA_NAME,
                    namespace=_EG_NAMESPACE,
                    labels={"app": "compassx"},
                )
            )
            k8s.core().create_namespaced_service_account(
                namespace=_EG_NAMESPACE, body=sa
            )
            logger.info("startup: created ServiceAccount %s", _SA_NAME)
        else:
            raise


def _ensure_cluster_role() -> None:
    rbac = get_k8s_client().rbac()
    rules = [
        k8s_client.V1PolicyRule(
            api_groups=[""],
            resources=["pods"],
            verbs=["get", "list", "watch"],
        ),
        k8s_client.V1PolicyRule(
            api_groups=[""],
            resources=["pods/exec"],
            verbs=["create", "get"],
        ),
        k8s_client.V1PolicyRule(
            api_groups=[""],
            resources=["pods/log"],
            verbs=["get"],
        ),
        k8s_client.V1PolicyRule(
            api_groups=[""],
            resources=["namespaces"],
            verbs=["get", "list"],
        ),
    ]
    cr = k8s_client.V1ClusterRole(
        metadata=k8s_client.V1ObjectMeta(
            name=_CLUSTER_ROLE_NAME,
            labels={"app": "compassx"},
        ),
        rules=rules,
    )
    try:
        rbac.replace_cluster_role(name=_CLUSTER_ROLE_NAME, body=cr)
        logger.debug("startup: updated ClusterRole %s", _CLUSTER_ROLE_NAME)
    except ApiException as exc:
        if exc.status == 404:
            rbac.create_cluster_role(body=cr)
            logger.info("startup: created ClusterRole %s", _CLUSTER_ROLE_NAME)
        else:
            raise


def _ensure_cluster_role_binding() -> None:
    rbac = get_k8s_client().rbac()
    binding_name = _CLUSTER_ROLE_NAME
    crb = k8s_client.V1ClusterRoleBinding(
        metadata=k8s_client.V1ObjectMeta(
            name=binding_name,
            labels={"app": "compassx"},
        ),
        subjects=[
            k8s_client.RbacV1Subject(
                kind="ServiceAccount",
                name=_SA_NAME,
                namespace=_EG_NAMESPACE,
            )
        ],
        role_ref=k8s_client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="ClusterRole",
            name=_CLUSTER_ROLE_NAME,
        ),
    )
    try:
        rbac.replace_cluster_role_binding(name=binding_name, body=crb)
        logger.debug("startup: updated ClusterRoleBinding %s", binding_name)
    except ApiException as exc:
        if exc.status == 404:
            rbac.create_cluster_role_binding(body=crb)
            logger.info("startup: created ClusterRoleBinding %s", binding_name)
        else:
            raise


def ensure_rbac() -> None:
    """Idempotent: create RBAC resources if missing."""
    try:
        _ensure_namespace(_EG_NAMESPACE)
        _ensure_namespace(_KERNEL_NAMESPACE)
        _ensure_service_account()
        _ensure_cluster_role()
        _ensure_cluster_role_binding()
        logger.info("startup: RBAC ready")
    except Exception as exc:
        logger.error("startup: RBAC setup failed: %s", exc)
        raise


# ── EG image ─────────────────────────────────────────────────────────────────

def _image_in_minikube(tag: str) -> bool:
    """Return True if tag already present in minikube's image cache."""
    result = subprocess.run(
        ["minikube", "image", "list"],
        capture_output=True, text=True,
    )
    # minikube image list returns names like "docker.io/library/foo:latest"
    # Normalise to bare name for matching.
    bare = tag.split("/")[-1]
    return any(bare in line for line in result.stdout.splitlines())


def _run(cmd: list[str], cwd: Path | None = None, **kwargs) -> None:
    logger.info("startup: running %s", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, **kwargs)


def _write_eg_image_to_env() -> None:
    """Ensure EG_IMAGE is set in .env so eg_settings picks it up on next load."""
    env_file = _BACKEND_DIR / ".env"
    if not env_file.exists():
        env_file.write_text(f"EG_IMAGE={_CUSTOM_IMAGE_TAG}\n", encoding="utf-8")
        return
    content = env_file.read_text(encoding="utf-8")
    if "EG_IMAGE=" in content:
        return
    with env_file.open("a", encoding="utf-8") as f:
        f.write(f"\nEG_IMAGE={_CUSTOM_IMAGE_TAG}\n")


def ensure_eg_image() -> None:
    """Build custom EG image and load into minikube if not already present."""
    if not _DOCKERFILE.exists():
        logger.error("startup: Dockerfile.eg not found at %s", _DOCKERFILE)
        raise FileNotFoundError(f"Dockerfile.eg not found: {_DOCKERFILE}")

    if _image_in_minikube(_CUSTOM_IMAGE_TAG):
        logger.info("startup: EG image %s already in minikube, skip build", _CUSTOM_IMAGE_TAG)
        _write_eg_image_to_env()
        eg_settings.EG_IMAGE = _CUSTOM_IMAGE_TAG
        return

    logger.info("startup: building EG image %s (first run, takes ~2 min)", _CUSTOM_IMAGE_TAG)
    _run(
        ["docker", "build", "-f", "Dockerfile.eg", "-t", _CUSTOM_IMAGE_TAG, "."],
        cwd=_BACKEND_DIR,
    )
    logger.info("startup: loading EG image into minikube")
    _run(["minikube", "image", "load", _CUSTOM_IMAGE_TAG])
    _write_eg_image_to_env()
    # Update the live settings object so any EG deployment created this session
    # uses the custom image without requiring a restart.
    eg_settings.EG_IMAGE = _CUSTOM_IMAGE_TAG
    logger.info("startup: EG image ready in minikube")


def ensure_airflow_image() -> None:
    """Pull Airflow image on host and load into minikube if not already present."""
    tag = airflow_settings.AIRFLOW_IMAGE
    if _image_in_minikube(tag):
        logger.info("startup: Airflow image %s already in minikube, skip pull", tag)
        return
    logger.info("startup: pulling Airflow image %s (may take a few minutes)", tag)
    _run(["docker", "pull", tag])
    logger.info("startup: loading Airflow image into minikube")
    _run(["minikube", "image", "load", tag])
    logger.info("startup: Airflow image ready in minikube")


def ensure_airflow_notebook_runner_image() -> None:
    """Build and load the dedicated notebook runner image."""
    tag = airflow_settings.AIRFLOW_NOTEBOOK_RUNNER_IMAGE
    if tag != _AIRFLOW_NOTEBOOK_IMAGE_TAG:
        logger.info("startup: notebook runner image is custom (%s), skipping local build", tag)
        return
    if not _AIRFLOW_NOTEBOOK_DOCKERFILE.exists():
        logger.error("startup: notebook runner Dockerfile not found at %s", _AIRFLOW_NOTEBOOK_DOCKERFILE)
        raise FileNotFoundError(f"Notebook runner Dockerfile not found: {_AIRFLOW_NOTEBOOK_DOCKERFILE}")
    if _image_in_minikube(tag):
        logger.info("startup: notebook runner image %s already in minikube, skip build", tag)
        return

    logger.info("startup: building notebook runner image %s", tag)
    _run(["docker", "build", "-f", "Dockerfile.airflow-notebook", "-t", tag, "."], cwd=_BACKEND_DIR)
    logger.info("startup: loading notebook runner image into minikube")
    _run(["minikube", "image", "load", tag])
    logger.info("startup: notebook runner image ready in minikube")


def ensure_airflow_local_assets() -> None:
    """Keep a local DAG workspace available only for debugging or migration."""
    dags_dir = Path(airflow_settings.AIRFLOW_DAGS_DIR)
    dags_dir.mkdir(parents=True, exist_ok=True)
    readme = dags_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Airflow DAGs\n\nDAGs are now written directly to object storage.\nUse this folder only for local debugging or migration helpers.\n",
            encoding="utf-8",
        )
    logger.info("startup: optional Airflow DAG workspace ready at %s", dags_dir)


def ensure_minio_local_assets() -> None:
    """Create local folders mirroring the persistent storage layout."""
    base = Path(airflow_settings.AIRFLOW_DAGS_DIR).parent
    (base / "dags").mkdir(parents=True, exist_ok=True)
    (base / "notebook-output").mkdir(parents=True, exist_ok=True)
    logger.info("startup: MinIO local assets ready under %s", base)


# ── Port-forward ─────────────────────────────────────────────────────────────

async def _wait_for_service(namespace: str, name: str) -> None:
    """Poll until the K8s Service exists (Jupyter Server may not be deployed yet)."""
    k8s = get_k8s_client()
    while True:
        try:
            await asyncio.to_thread(
                k8s.core().read_namespaced_service, name=name, namespace=namespace
            )
            return
        except ApiException as exc:
            if exc.status == 404:
                logger.debug(
                    "startup: waiting for service %s/%s to be created...", namespace, name
                )
                await asyncio.sleep(10)
            else:
                raise
        except Exception as exc:
            logger.debug("startup: service check error: %s, retrying in 10s", exc)
            await asyncio.sleep(10)


async def _wait_for_pod_by_label(namespace: str, label_selector: str) -> str:
    """Poll until a Running pod matching the label selector exists."""
    k8s = get_k8s_client()
    while True:
        try:
            pods = await asyncio.to_thread(
                k8s.core().list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector,
            )
            for pod in pods.items:
                phase = pod.status.phase if pod.status else None
                name = pod.metadata.name if pod.metadata else None
                if name and phase == "Running":
                    return name
            logger.debug(
                "startup: waiting for running pod in %s with labels %s...",
                namespace,
                label_selector,
            )
            await asyncio.sleep(10)
        except Exception as exc:
            logger.debug("startup: pod check error: %s, retrying in 10s", exc)
            await asyncio.sleep(10)


async def _port_forward_loop() -> None:
    """Keep kubectl port-forward alive.

    Waits for the Jupyter Server service to exist first (user may not have
    started it yet), then maintains the forward indefinitely, restarting on
    exit so pod restarts don't break the connection.
    """
    global _pf_process

    _pf_log("info", "Jupyter Server", "WAITING_SERVICE", "waiting for service %s/%s", _EG_NAMESPACE, _JS_SERVICE_NAME)
    await _wait_for_service(_EG_NAMESPACE, _JS_SERVICE_NAME)
    await asyncio.to_thread(_kill_stale_port_forward, _JS_LOCAL_PORT)

    while True:
        try:
            if await asyncio.to_thread(_kubectl_forward_is_healthy, _JS_LOCAL_PORT):
                _pf_log("info", "Jupyter Server", "HEALTHY", "localhost:%s is accepting connections", _JS_LOCAL_PORT)
                await asyncio.sleep(10)
                continue
            if await asyncio.to_thread(_has_kubectl_listener, _JS_LOCAL_PORT):
                _pf_log("warning", "Jupyter Server", "BROKEN", "localhost:%s has a kubectl listener but is not accepting connections; restarting", _JS_LOCAL_PORT)
                await asyncio.to_thread(_kill_stale_port_forward, _JS_LOCAL_PORT)
            await asyncio.to_thread(_terminate_process, _pf_process)
            _pf_log("info", "Jupyter Server", "STARTING", "kubectl port-forward svc/%s %s:%s -n %s", _JS_SERVICE_NAME, _JS_LOCAL_PORT, _JS_LOCAL_PORT, _EG_NAMESPACE)
            logger.info(
                "startup: starting port-forward %s/%s → localhost:%s",
                _EG_NAMESPACE, _JS_SERVICE_NAME, _JS_LOCAL_PORT,
            )
            # Use a normal subprocess here because Windows uvicorn commonly runs
            # on a selector loop, which cannot spawn asyncio subprocesses.
            _pf_process = subprocess.Popen(
                [
                    "kubectl", "port-forward",
                    f"svc/{_JS_SERVICE_NAME}",
                    f"{_JS_LOCAL_PORT}:8888",
                    "-n", _EG_NAMESPACE,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _pf_log("info", "Jupyter Server", "RUNNING", "pid=%s localhost:%s -> svc/%s:8888", _pf_process.pid, _JS_LOCAL_PORT, _JS_SERVICE_NAME)
            rc = await asyncio.to_thread(_pf_process.wait)
            stderr = b""
            if _pf_process.stderr is not None:
                stderr = await asyncio.to_thread(_pf_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "Jupyter Server", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "Jupyter Server", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "Jupyter Server", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _pf_process = None

        await asyncio.sleep(1)


async def _eg_port_forward_loop() -> None:
    """Keep kubectl port-forward to EG alive (localhost:{EG_PORT} → cluster EG service)."""
    global _eg_pf_process

    _pf_log("info", "Enterprise Gateway", "WAITING_SERVICE", "waiting for service %s/%s", _EG_NAMESPACE, _EG_SERVICE_NAME)
    await _wait_for_service(_EG_NAMESPACE, _EG_SERVICE_NAME)
    await asyncio.to_thread(_kill_stale_port_forward, _EG_LOCAL_PORT)

    while True:
        try:
            if await asyncio.to_thread(_kubectl_forward_is_healthy, _EG_LOCAL_PORT):
                _pf_log("info", "Enterprise Gateway", "HEALTHY", "localhost:%s is accepting connections", _EG_LOCAL_PORT)
                await asyncio.sleep(10)
                continue
            if await asyncio.to_thread(_has_kubectl_listener, _EG_LOCAL_PORT):
                _pf_log("warning", "Enterprise Gateway", "BROKEN", "localhost:%s has a kubectl listener but is not accepting connections; restarting", _EG_LOCAL_PORT)
                await asyncio.to_thread(_kill_stale_port_forward, _EG_LOCAL_PORT)
            await asyncio.to_thread(_terminate_process, _eg_pf_process)
            _pf_log("info", "Enterprise Gateway", "STARTING", "kubectl port-forward svc/%s %s:%s -n %s", _EG_SERVICE_NAME, _EG_LOCAL_PORT, _EG_LOCAL_PORT, _EG_NAMESPACE)
            logger.info(
                "startup: starting EG port-forward %s/%s → localhost:%s",
                _EG_NAMESPACE, _EG_SERVICE_NAME, _EG_LOCAL_PORT,
            )
            _eg_pf_process = subprocess.Popen(
                [
                    "kubectl", "port-forward",
                    f"svc/{_EG_SERVICE_NAME}",
                    f"{_EG_LOCAL_PORT}:{_EG_LOCAL_PORT}",
                    "-n", _EG_NAMESPACE,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _pf_log("info", "Enterprise Gateway", "RUNNING", "pid=%s localhost:%s -> svc/%s:%s", _eg_pf_process.pid, _EG_LOCAL_PORT, _EG_SERVICE_NAME, _EG_LOCAL_PORT)
            rc = await asyncio.to_thread(_eg_pf_process.wait)
            stderr = b""
            if _eg_pf_process.stderr is not None:
                stderr = await asyncio.to_thread(_eg_pf_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "Enterprise Gateway", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "Enterprise Gateway", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "Enterprise Gateway", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _eg_pf_process = None

        await asyncio.sleep(1)



async def _backend_port_forward_loop() -> None:
    """Keep kubectl port-forward to the backend service alive when host mode needs pod mode."""
    global _backend_pf_process

    if not get_backend_runtime_manager().backend_port_forward_required():
        return

    _pf_log("info", "Backend", "WAITING_SERVICE", "waiting for service %s/%s", BACKEND_NAMESPACE, BACKEND_SERVICE_NAME)
    await _wait_for_service(BACKEND_NAMESPACE, BACKEND_SERVICE_NAME)
    await asyncio.to_thread(_kill_stale_port_forward, BACKEND_LOCAL_PORT)

    while True:
        try:
            if await asyncio.to_thread(_kubectl_forward_is_healthy, BACKEND_LOCAL_PORT):
                _pf_log("info", "Backend", "HEALTHY", "localhost:%s is accepting connections", BACKEND_LOCAL_PORT)
                mark_backend_port_forward_ready()
                await asyncio.sleep(10)
                continue
            if await asyncio.to_thread(_has_kubectl_listener, BACKEND_LOCAL_PORT):
                _pf_log("warning", "Backend", "BROKEN", "localhost:%s has a kubectl listener but is not accepting connections; restarting", BACKEND_LOCAL_PORT)
                await asyncio.to_thread(_kill_stale_port_forward, BACKEND_LOCAL_PORT)
            await asyncio.to_thread(_terminate_process, _backend_pf_process)
            _pf_log("info", "Backend", "STARTING", "kubectl port-forward svc/%s %s:%s -n %s", BACKEND_SERVICE_NAME, BACKEND_LOCAL_PORT, BACKEND_PORT, BACKEND_NAMESPACE)
            logger.info(
                "startup: starting backend port-forward %s/%s -> localhost:%s",
                BACKEND_NAMESPACE, BACKEND_SERVICE_NAME, BACKEND_LOCAL_PORT,
            )
            _backend_pf_process = subprocess.Popen([
                "kubectl", "port-forward",
                f"svc/{BACKEND_SERVICE_NAME}",
                f"{BACKEND_LOCAL_PORT}:{BACKEND_PORT}",
                "-n", BACKEND_NAMESPACE,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _pf_log("info", "Backend", "RUNNING", "pid=%s localhost:%s -> svc/%s:%s", _backend_pf_process.pid, BACKEND_LOCAL_PORT, BACKEND_SERVICE_NAME, BACKEND_PORT)
            mark_backend_port_forward_ready()
            rc = await asyncio.to_thread(_backend_pf_process.wait)
            stderr = b""
            if _backend_pf_process.stderr is not None:
                stderr = await asyncio.to_thread(_backend_pf_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "Backend", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "Backend", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "Backend", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _backend_pf_process = None
            clear_backend_port_forward_ready()

        await asyncio.sleep(1)

async def _airflow_port_forward_loop() -> None:
    """Keep kubectl port-forward to Airflow alive."""
    global _airflow_pf_process

    _pf_log("info", "Airflow", "WAITING_SERVICE", "waiting for service %s/%s", airflow_settings.AIRFLOW_NAMESPACE, _AIRFLOW_SERVICE_NAME)
    await _wait_for_service(airflow_settings.AIRFLOW_NAMESPACE, _AIRFLOW_SERVICE_NAME)
    await asyncio.to_thread(_kill_stale_port_forward, _AIRFLOW_LOCAL_PORT)

    while True:
        try:
            if await asyncio.to_thread(_kubectl_forward_is_healthy, _AIRFLOW_LOCAL_PORT):
                _pf_log("info", "Airflow", "HEALTHY", "localhost:%s is accepting connections", _AIRFLOW_LOCAL_PORT)
                await asyncio.sleep(10)
                continue
            if await asyncio.to_thread(_has_kubectl_listener, _AIRFLOW_LOCAL_PORT):
                _pf_log("warning", "Airflow", "BROKEN", "localhost:%s has a kubectl listener but is not accepting connections; restarting", _AIRFLOW_LOCAL_PORT)
                await asyncio.to_thread(_kill_stale_port_forward, _AIRFLOW_LOCAL_PORT)
            await asyncio.to_thread(_terminate_process, _airflow_pf_process)
            _pf_log("info", "Airflow", "STARTING", "kubectl port-forward svc/%s %s:%s -n %s", _AIRFLOW_SERVICE_NAME, _AIRFLOW_LOCAL_PORT, _AIRFLOW_LOCAL_PORT, airflow_settings.AIRFLOW_NAMESPACE)
            logger.info(
                "startup: starting Airflow port-forward %s/%s -> localhost:%s",
                airflow_settings.AIRFLOW_NAMESPACE, _AIRFLOW_SERVICE_NAME, _AIRFLOW_LOCAL_PORT,
            )
            _airflow_pf_process = subprocess.Popen(
                [
                    "kubectl", "port-forward",
                    f"svc/{_AIRFLOW_SERVICE_NAME}",
                    f"{_AIRFLOW_LOCAL_PORT}:{_AIRFLOW_LOCAL_PORT}",
                    "-n", airflow_settings.AIRFLOW_NAMESPACE,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _pf_log("info", "Airflow", "RUNNING", "pid=%s localhost:%s -> svc/%s:%s", _airflow_pf_process.pid, _AIRFLOW_LOCAL_PORT, _AIRFLOW_SERVICE_NAME, _AIRFLOW_LOCAL_PORT)
            rc = await asyncio.to_thread(_airflow_pf_process.wait)
            stderr = b""
            if _airflow_pf_process.stderr is not None:
                stderr = await asyncio.to_thread(_airflow_pf_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "Airflow", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "Airflow", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "Airflow", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _airflow_pf_process = None

        await asyncio.sleep(1)


async def _minio_port_forward_loop() -> None:
    global _minio_pf_process

    _pf_log("info", "MinIO API", "WAITING_SERVICE", "waiting for service %s/%s", minio_settings.MINIO_NAMESPACE, _MINIO_SERVICE_NAME)
    await _wait_for_service(minio_settings.MINIO_NAMESPACE, _MINIO_SERVICE_NAME)
    await asyncio.to_thread(_kill_stale_port_forward, _MINIO_LOCAL_PORT)

    while True:
        try:
            if await asyncio.to_thread(_kubectl_forward_is_healthy, _MINIO_LOCAL_PORT):
                _pf_log("info", "MinIO API", "HEALTHY", "localhost:%s is accepting connections", _MINIO_LOCAL_PORT)
                await asyncio.sleep(10)
                continue
            if await asyncio.to_thread(_has_kubectl_listener, _MINIO_LOCAL_PORT):
                _pf_log("warning", "MinIO API", "BROKEN", "localhost:%s has a kubectl listener but is not accepting connections; restarting", _MINIO_LOCAL_PORT)
                await asyncio.to_thread(_kill_stale_port_forward, _MINIO_LOCAL_PORT)
            await asyncio.to_thread(_terminate_process, _minio_pf_process)
            _pf_log("info", "MinIO API", "STARTING", "kubectl port-forward svc/%s %s:%s -n %s", _MINIO_SERVICE_NAME, _MINIO_LOCAL_PORT, _MINIO_LOCAL_PORT, minio_settings.MINIO_NAMESPACE)
            logger.info(
                "startup: starting MinIO port-forward %s/%s -> localhost:%s",
                minio_settings.MINIO_NAMESPACE, _MINIO_SERVICE_NAME, _MINIO_LOCAL_PORT,
            )
            _minio_pf_process = subprocess.Popen(
                [
                    "kubectl", "port-forward",
                    f"svc/{_MINIO_SERVICE_NAME}",
                    f"{_MINIO_LOCAL_PORT}:{_MINIO_LOCAL_PORT}",
                    "-n", minio_settings.MINIO_NAMESPACE,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _pf_log("info", "MinIO API", "RUNNING", "pid=%s localhost:%s -> svc/%s:%s", _minio_pf_process.pid, _MINIO_LOCAL_PORT, _MINIO_SERVICE_NAME, _MINIO_LOCAL_PORT)
            rc = await asyncio.to_thread(_minio_pf_process.wait)
            stderr = b""
            if _minio_pf_process.stderr is not None:
                stderr = await asyncio.to_thread(_minio_pf_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "MinIO API", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "MinIO API", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "MinIO API", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _minio_pf_process = None

        await asyncio.sleep(1)


async def _minio_console_port_forward_loop() -> None:
    global _minio_console_pf_process

    _pf_log("info", "MinIO Console", "WAITING_SERVICE", "waiting for service %s/%s", minio_settings.MINIO_NAMESPACE, _MINIO_CONSOLE_SERVICE_NAME)
    await _wait_for_service(minio_settings.MINIO_NAMESPACE, _MINIO_CONSOLE_SERVICE_NAME)
    await asyncio.to_thread(_kill_stale_port_forward, _MINIO_CONSOLE_LOCAL_PORT)

    while True:
        try:
            if await asyncio.to_thread(_kubectl_forward_is_healthy, _MINIO_CONSOLE_LOCAL_PORT):
                _pf_log("info", "MinIO Console", "HEALTHY", "localhost:%s is accepting connections", _MINIO_CONSOLE_LOCAL_PORT)
                await asyncio.sleep(10)
                continue
            if await asyncio.to_thread(_has_kubectl_listener, _MINIO_CONSOLE_LOCAL_PORT):
                _pf_log("warning", "MinIO Console", "BROKEN", "localhost:%s has a kubectl listener but is not accepting connections; restarting", _MINIO_CONSOLE_LOCAL_PORT)
                await asyncio.to_thread(_kill_stale_port_forward, _MINIO_CONSOLE_LOCAL_PORT)
            await asyncio.to_thread(_terminate_process, _minio_console_pf_process)
            _pf_log("info", "MinIO Console", "STARTING", "kubectl port-forward svc/%s %s:%s -n %s", _MINIO_CONSOLE_SERVICE_NAME, _MINIO_CONSOLE_LOCAL_PORT, minio_settings.MINIO_CONSOLE_PORT, minio_settings.MINIO_NAMESPACE)
            logger.info(
                "startup: starting MinIO console port-forward %s/%s -> localhost:%s",
                minio_settings.MINIO_NAMESPACE, _MINIO_CONSOLE_SERVICE_NAME, _MINIO_CONSOLE_LOCAL_PORT,
            )
            _minio_console_pf_process = subprocess.Popen(
                [
                    "kubectl", "port-forward",
                    f"svc/{_MINIO_CONSOLE_SERVICE_NAME}",
                    f"{_MINIO_CONSOLE_LOCAL_PORT}:{minio_settings.MINIO_CONSOLE_PORT}",
                    "-n", minio_settings.MINIO_NAMESPACE,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _pf_log("info", "MinIO Console", "RUNNING", "pid=%s localhost:%s -> svc/%s:%s", _minio_console_pf_process.pid, _MINIO_CONSOLE_LOCAL_PORT, _MINIO_CONSOLE_SERVICE_NAME, minio_settings.MINIO_CONSOLE_PORT)
            rc = await asyncio.to_thread(_minio_console_pf_process.wait)
            stderr = b""
            if _minio_console_pf_process.stderr is not None:
                stderr = await asyncio.to_thread(_minio_console_pf_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "MinIO Console", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "MinIO Console", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "MinIO Console", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _minio_console_pf_process = None

        await asyncio.sleep(1)


async def _minio_tunnel_loop() -> None:
    global _minio_tunnel_process

    _pf_log("info", "MinIO Tunnel", "WAITING_SERVICE", "waiting for service %s/%s", minio_settings.MINIO_NAMESPACE, _MINIO_CONSOLE_SERVICE_NAME)
    await _wait_for_service(minio_settings.MINIO_NAMESPACE, _MINIO_CONSOLE_SERVICE_NAME)

    while True:
        try:
            await asyncio.to_thread(_terminate_process, _minio_tunnel_process)
            _pf_log("info", "MinIO Tunnel", "STARTING", "minikube tunnel for MinIO local access")
            _minio_tunnel_process = subprocess.Popen(
                ["minikube", "tunnel"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _pf_log("info", "MinIO Tunnel", "RUNNING", "pid=%s", _minio_tunnel_process.pid)
            rc = await asyncio.to_thread(_minio_tunnel_process.wait)
            stderr = b""
            if _minio_tunnel_process.stderr is not None:
                stderr = await asyncio.to_thread(_minio_tunnel_process.stderr.read)
            if stderr:
                err = stderr.decode(errors="replace").strip()
                _pf_log("warning", "MinIO Tunnel", "EXITED", "rc=%s stderr=%s; retrying in 1s", rc, err)
            else:
                _pf_log("warning", "MinIO Tunnel", "EXITED", "rc=%s; restarting in 1s", rc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _pf_log("warning", "MinIO Tunnel", "ERROR", "%s; retrying in 1s", exc)
        finally:
            _minio_tunnel_process = None

        await asyncio.sleep(1)


def start_port_forward() -> None:
    """Schedule the port-forward loops as background asyncio tasks."""
    global _pf_task, _eg_pf_task, _backend_pf_task, _airflow_pf_task, _minio_pf_task, _minio_console_pf_task, _minio_tunnel_task
    loop = asyncio.get_event_loop()
    if _pf_task is None or _pf_task.done():
        _pf_task = loop.create_task(_port_forward_loop())
        _pf_log("info", "Jupyter Server", "SCHEDULED", "background task scheduled")
    if _eg_pf_task is None or _eg_pf_task.done():
        _eg_pf_task = loop.create_task(_eg_port_forward_loop())
        _pf_log("info", "Enterprise Gateway", "SCHEDULED", "background task scheduled")
    if _backend_pf_task is None or _backend_pf_task.done():
        _backend_pf_task = loop.create_task(_backend_port_forward_loop())
        _pf_log("info", "Backend", "SCHEDULED", "background task scheduled")


def stop_port_forward() -> None:
    """Cancel background port-forwards on app shutdown."""
    global _pf_task, _pf_process, _eg_pf_task, _eg_pf_process, _backend_pf_task, _backend_pf_process, _airflow_pf_task, _airflow_pf_process, _minio_pf_task, _minio_pf_process, _minio_console_pf_task, _minio_console_pf_process, _minio_tunnel_task, _minio_tunnel_process
    for task_name in ("_pf_task", "_eg_pf_task", "_backend_pf_task", "_airflow_pf_task", "_minio_pf_task", "_minio_console_pf_task", "_minio_tunnel_task"):
        task = globals().get(task_name)
        if task:
            task.cancel()
            globals()[task_name] = None
    for proc_name in ("_pf_process", "_eg_pf_process", "_backend_pf_process", "_airflow_pf_process", "_minio_pf_process", "_minio_console_pf_process", "_minio_tunnel_process"):
        proc = globals().get(proc_name)
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
            globals()[proc_name] = None

    _pf_log("info", "all", "STOPPED", "background port-forward processes stopped")


async def run_startup_tasks() -> None:
    """Called from FastAPI lifespan.  Runs blocking steps in thread pool."""
    loop = asyncio.get_event_loop()

    if compute_settings.backend_runtime_is_pod():
        try:
            manager = get_backend_runtime_manager()
            await loop.run_in_executor(None, manager.ensure_backend_pod)
            ready = await loop.run_in_executor(None, manager.wait_until_ready)
            if not ready:
                logger.warning("startup: backend pod did not become ready before timeout")
        except Exception as exc:
            logger.error("startup: backend pod provision failed (non-fatal): %s", exc)
    elif compute_settings.is_local():
        logger.info(
            "startup: local K8s bootstrap disabled; skipping minikube/RBAC/service deploy/port-forward automation"
        )
    else:
        logger.info("startup: k8s mode detected, skipping local-only minikube/docker/port-forward bootstrap")

    # Temporarily disabled: port-forward automation is kept here for easy re-enable.
    # start_port_forward()

    try:
        from app.database import SessionLocal, is_db_available
        from compute.resource_service import ComputeResourceService

        if is_db_available() and SessionLocal is not None:
            def _bootstrap_default_compute() -> None:
                db = SessionLocal()
                try:
                    ComputeResourceService(db).ensure_default_resource()
                finally:
                    db.close()

            await loop.run_in_executor(None, _bootstrap_default_compute)
        else:
            logger.warning("startup: database unavailable, skipping default compute bootstrap")
    except Exception as exc:
        logger.error("startup: default compute bootstrap failed (non-fatal): %s", exc)

    # Port-forward — async loop, won't block
    logger.info("startup: all tasks complete")









