"""CompassXProcessProxy — standalone module bundled into the custom EG image.

This file is copied into the EG Docker image (see Dockerfile.eg) so that
Enterprise Gateway can import it. It must NOT import anything from the
CompassX backend codebase — all config comes from environment variables.

Environment variables read at runtime:
  COMPASSX_JOB_ID      — injected by useKernel.ts via kernel env
  KERNEL_NAMESPACE     — K8s namespace where compute pods run (default: compassx-jobs)
  EG_CONNECTION_FILE_PATH — where to write ZMQ connection file (default: /tmp)
  EG_KERNEL_LAUNCH_TIMEOUT — seconds to wait for kernel to start (default: 120)
  COMPASSX_JOB_ID_LABEL   — pod label key for job lookup (default: compassx/job)
"""
import asyncio
import json
import logging
import os
import threading
import time
from typing import Optional

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes import stream as k8s_stream
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

# Config from env
KERNEL_NAMESPACE = os.environ.get("KERNEL_NAMESPACE", "compassx-jobs")
EG_CONNECTION_FILE_PATH = os.environ.get("EG_CONNECTION_FILE_PATH", "/tmp")
EG_KERNEL_LAUNCH_TIMEOUT = int(os.environ.get("EG_KERNEL_LAUNCH_TIMEOUT", "120"))
JOB_ID_LABEL = os.environ.get("COMPASSX_JOB_ID_LABEL", "compassx/job")


def _load_k8s_config() -> None:
    """Load K8s config — prefer explicit KUBECONFIG file, fall back to in-cluster."""
    if os.environ.get("KUBECONFIG") or os.path.exists(
        os.path.expanduser("~/.kube/config")
    ):
        k8s_config.load_kube_config()
    else:
        k8s_config.load_incluster_config()


_k8s_loaded = False


def _ensure_k8s() -> None:
    global _k8s_loaded
    if not _k8s_loaded:
        _load_k8s_config()
        _k8s_loaded = True


# enterprise_gateway/processproxies/k8s.py calls load_incluster_config() at module
# level. When EG runs outside a cluster (local Docker testing), this raises
# ConfigException before our code runs. Inject dummy env + stub files so the
# module-level call succeeds; _load_k8s_config() at runtime overrides with kubeconfig.
_SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
if not os.environ.get("KUBERNETES_SERVICE_HOST"):
    os.environ.setdefault("KUBERNETES_SERVICE_HOST", "127.0.0.1")
    os.environ.setdefault("KUBERNETES_SERVICE_PORT", "443")
    if not os.path.exists(f"{_SA_DIR}/token"):
        try:
            import pathlib
            pathlib.Path(_SA_DIR).mkdir(parents=True, exist_ok=True)
            pathlib.Path(f"{_SA_DIR}/token").write_text("dummy-token")
            pathlib.Path(f"{_SA_DIR}/ca.crt").write_text(
                "-----BEGIN CERTIFICATE-----\ndummy\n-----END CERTIFICATE-----\n"
            )
            pathlib.Path(f"{_SA_DIR}/namespace").write_text(
                os.environ.get("KERNEL_NAMESPACE", "compassx-jobs")
            )
        except OSError:
            pass  # Container may not have write access; import will fail gracefully

try:
    from enterprise_gateway.services.processproxies.k8s import KubernetesProcessProxy
    _EG_AVAILABLE = True
except (ImportError, Exception):
    _EG_AVAILABLE = False
    KubernetesProcessProxy = object  # type: ignore


class CompassXProcessProxy(KubernetesProcessProxy):  # type: ignore
    """Execs ipykernel into an existing CompassX compute pod.

    Instead of launching a new pod per kernel, finds the pod by
    compassx/job label and execs ipykernel_launcher inside it.
    Killing a kernel does not delete the underlying compute pod.
    """

    def __init__(self, kernel_manager, proxy_config):
        super().__init__(kernel_manager, proxy_config)
        self.pod_name: str | None = None
        self.pod_ip: str | None = None
        self.job_id: str | None = None
        self.local_conn: str | None = None

    async def launch_process(self, kernel_cmd: list, **kwargs) -> "CompassXProcessProxy":
        """Find compute pod and exec ipykernel into it."""
        _ensure_k8s()
        env = kwargs.get("env", {}) or {}

        # EG 3.x automatically forwards env vars prefixed with KERNEL_ from the
        # request body to the process proxy. Plain COMPASSX_JOB_ID is stripped
        # unless whitelisted (unreliable). Use KERNEL_COMPASSX_JOB_ID instead.
        # Accept both for backwards-compatibility during transition.
        job_id = env.get("KERNEL_COMPASSX_JOB_ID") or env.get("COMPASSX_JOB_ID")
        if not job_id:
            raise RuntimeError(
                "KERNEL_COMPASSX_JOB_ID is required. Select a running compute pod in the notebook toolbar."
            )

        pod = self._get_pod(job_id)
        pod_name = pod.metadata.name
        pod_ip = pod.status.pod_ip

        conn_file = f"{EG_CONNECTION_FILE_PATH}/kernel-{self.kernel_id}.json"
        session_token = env.get("KERNEL_NOTEBOOK_SESSION_TOKEN") or env.get("NOTEBOOK_SESSION_TOKEN") or ""
        catalog_url = env.get("KERNEL_CATALOG_API_URL") or env.get("CATALOG_API_URL") or ""
        workspace_id = env.get("KERNEL_WORKSPACE_ID") or env.get("WORKSPACE_ID") or ""
        workspace_slug = env.get("KERNEL_WORKSPACE_SLUG") or env.get("WORKSPACE_SLUG") or ""
        if catalog_url.startswith(("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
            host_gateway = os.environ.get("COMPASSX_HOST_GATEWAY", "host.docker.internal")
            catalog_url = catalog_url.replace("localhost", host_gateway).replace("127.0.0.1", host_gateway)
        command = [
            "python", "-c",
            (
                "import sys, os; "
                f"os.environ['NOTEBOOK_SESSION_TOKEN'] = {session_token!r}; "
                f"os.environ['KERNEL_NOTEBOOK_SESSION_TOKEN'] = {session_token!r}; "
                f"os.environ['CATALOG_API_URL'] = {catalog_url!r}; "
                f"os.environ['KERNEL_CATALOG_API_URL'] = {catalog_url!r}; "
                f"os.environ['WORKSPACE_ID'] = {workspace_id!r}; "
                f"os.environ['KERNEL_WORKSPACE_ID'] = {workspace_id!r}; "
                f"os.environ['WORKSPACE_SLUG'] = {workspace_slug!r}; "
                f"os.environ['KERNEL_WORKSPACE_SLUG'] = {workspace_slug!r}; "
                f"sys.argv = ['ipykernel_launcher', '--ip=0.0.0.0', '--InteractiveShellApp.exec_lines', 'import services.compassx_sql as cx', '--InteractiveShellApp.exec_lines', '%load_ext services.compassx_sql', '-f', '{conn_file}']; "
                "import services.fsspec_cx; "
                "from ipykernel import kernelapp; kernelapp.main()"
            ),
        ]

        logger.info("Execing ipykernel into pod %s kernel_id=%s", pod_name, self.kernel_id)

        asyncio.get_running_loop().run_in_executor(None, self._exec_in_pod_background, pod_name, command)

        # Poll until connection file exists and has content, then read it in one step.
        # Using `test -s` (non-empty) + `cat` so we get the content only when ready.
        # A plain `test -f` produces no stdout regardless of exit code, so we can't
        # rely on it to detect success via _exec_in_pod's string-based return.
        conn_json = ""
        start = time.monotonic()
        while time.monotonic() - start < EG_KERNEL_LAUNCH_TIMEOUT:
            await asyncio.sleep(0.5)
            try:
                conn_json = self._exec_in_pod(
                    pod_name,
                    ["sh", "-c", f"test -s {conn_file} && cat {conn_file}"],
                    timeout=5,
                )
                if conn_json.strip():
                    break
            except Exception:
                pass
        else:
            raise RuntimeError(
                f"Kernel failed to start in pod {pod_name} within {EG_KERNEL_LAUNCH_TIMEOUT}s. "
                "Ensure ipykernel is installed in the pod image."
            )

        conn_info = json.loads(conn_json)
        conn_info["ip"] = pod_ip

        logger.info(
            "Kernel ready in pod %s at %s ports=%s",
            pod_name, pod_ip,
            {k: v for k, v in conn_info.items() if k.endswith("_port")},
        )

        # Push connection info into kernel_manager so EG builds ZMQ sockets
        # to the pod IP/ports rather than the default tcp://0.0.0.0:0.
        km = self.kernel_manager
        km.ip = pod_ip
        km.shell_port = conn_info["shell_port"]
        km.iopub_port = conn_info["iopub_port"]
        km.stdin_port = conn_info["stdin_port"]
        km.control_port = conn_info["control_port"]
        km.hb_port = conn_info["hb_port"]
        # The kernel in the pod signed its messages with the key from its own
        # connection file. Sync that key into the session so HMAC verification
        # passes. Session.key must be bytes.
        pod_key = conn_info.get("key", "")
        if pod_key and hasattr(km, "session"):
            km.session.key = pod_key.encode() if isinstance(pod_key, str) else pod_key
        # Rewrite the connection file EG will read so all channels point to pod.
        with open(km.connection_file, "w") as fh:
            json.dump(conn_info, fh)

        self.pod_name = pod_name
        self.pod_ip = pod_ip
        self.job_id = job_id
        self.local_conn = km.connection_file
        return self

    def poll(self) -> Optional[int]:
        if not self.pod_name:
            return 1
        try:
            self._exec_in_pod(
                self.pod_name,
                ["pgrep", "-f", f"kernel-{self.kernel_id}.json"],
                timeout=10,
            )
            return None
        except RuntimeError:
            return 1
        except Exception:
            return None

    def kill(self, restart: bool = False) -> None:
        if not self.pod_name:
            return
        try:
            pid_output = self._exec_in_pod(
                self.pod_name,
                ["pgrep", "-f", f"kernel-{self.kernel_id}.json"],
                timeout=10,
            )
            pid = pid_output.strip().split()[0]
            self._exec_in_pod(self.pod_name, ["kill", "-9", pid], timeout=10)
        except Exception as exc:
            logger.warning("Could not kill kernel in pod %s: %s", self.pod_name, exc)

        try:
            conn_path = f"{EG_CONNECTION_FILE_PATH}/kernel-{self.kernel_id}.json"
            self._exec_in_pod(self.pod_name, ["rm", "-f", conn_path], timeout=10)
        except Exception:
            pass

        if self.local_conn and os.path.exists(self.local_conn):
            try:
                os.remove(self.local_conn)
            except OSError:
                pass

        logger.info("Kernel %s killed in pod %s", self.kernel_id, self.pod_name)

    def send_signal(self, signum: int) -> None:
        if not self.pod_name:
            return
        try:
            pid_output = self._exec_in_pod(
                self.pod_name,
                ["pgrep", "-f", f"kernel-{self.kernel_id}.json"],
                timeout=10,
            )
            pid = pid_output.strip().split()[0]
            self._exec_in_pod(self.pod_name, ["kill", f"-{signum}", pid], timeout=10)
        except Exception as exc:
            logger.warning("send_signal(%s) failed for kernel %s: %s", signum, self.kernel_id, exc)

    def _core_api(self) -> k8s_client.CoreV1Api:
        """Return a CoreV1Api with a fresh connection each call to avoid stale pools."""
        _ensure_k8s()
        return k8s_client.CoreV1Api(k8s_client.ApiClient())

    def _exec_in_pod(self, pod_name: str, command: list[str], timeout: int = 30) -> str:
        core = self._core_api()
        # _preload_content=False returns a WSClient whose read_all() blocks until
        # the command exits and returns all stdout as a string.
        ws = k8s_stream.stream(
            core.connect_get_namespaced_pod_exec,
            pod_name,
            KERNEL_NAMESPACE,
            command=command,
            stderr=False,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
            _request_timeout=timeout,
        )
        try:
            ws.run_forever(timeout=timeout)
            return ws.read_all()
        finally:
            ws.close()

    def _exec_in_pod_background(self, pod_name: str, command: list[str]) -> None:
        try:
            self._exec_in_pod(pod_name, command, timeout=EG_KERNEL_LAUNCH_TIMEOUT + 10)
        except Exception as exc:
            logger.debug("Background exec completed/errored (expected): %s", exc)

    def _get_pod(self, job_id: str) -> k8s_client.V1Pod:
        core = self._core_api()
        try:
            pods = core.list_namespaced_pod(
                namespace=KERNEL_NAMESPACE,
                label_selector=f"{JOB_ID_LABEL}={job_id}",
            )
        except ApiException as exc:
            raise RuntimeError(f"K8s API error looking up pod for job {job_id}: {exc}") from exc

        if not pods.items:
            raise RuntimeError(
                f"Compute pod for job {job_id} not found. "
                "Ensure the pod is running before connecting a kernel."
            )

        pod = pods.items[0]
        phase = pod.status.phase if pod.status and pod.status.phase else "Unknown"
        if phase != "Running":
            raise RuntimeError(
                f"Compute pod for job {job_id} is {phase}. "
                "Wait for it to reach Running state."
            )

        return pod
