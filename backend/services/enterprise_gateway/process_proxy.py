"""CompassXProcessProxy — execs ipykernel into an existing compute pod.

Extends KubernetesProcessProxy from enterprise-gateway.
Instead of creating a new pod for each kernel, this proxy:
  1. Finds the existing compute pod by compassx/job label
  2. Execs ipykernel_launcher inside that pod via K8s API
  3. Reads the ZMQ connection file back from the pod
  4. Returns connection info to Enterprise Gateway

The compute pod (Spark/Ray/Flink/DuckDB) keeps running independently.
Killing a kernel does not affect the underlying runtime process.
"""
import asyncio
import json
import logging
import os
import time
from typing import Optional

from kubernetes import client as k8s_client
from kubernetes import stream as k8s_stream
from kubernetes.client.exceptions import ApiException

from services.enterprise_gateway.config import eg_settings, JOB_ID_LABEL

logger = logging.getLogger(__name__)

try:
    from enterprise_gateway.services.processproxies.k8s import KubernetesProcessProxy
    _EG_AVAILABLE = True
except ImportError:
    # Allow module to load even if EG not installed (e.g. during tests)
    _EG_AVAILABLE = False
    KubernetesProcessProxy = object  # type: ignore


class CompassXProcessProxy(KubernetesProcessProxy):  # type: ignore
    """Custom EG process proxy that execs ipykernel into existing compute pods."""

    def __init__(self, kernel_manager, proxy_config):
        super().__init__(kernel_manager, proxy_config)
        self.pod_name: str | None = None
        self.pod_ip: str | None = None
        self.job_id: str | None = None
        self.local_conn: str | None = None

    async def launch_process(self, kernel_cmd: list, **kwargs) -> "CompassXProcessProxy":
        """Called by EG when a kernel start is requested.

        Flow:
          1. Extract COMPASSX_JOB_ID from env
          2. Find compute pod by label
          3. Exec ipykernel_launcher inside pod (non-blocking)
          4. Poll for connection file
          5. Read and parse connection file
          6. Replace ip with pod IP
          7. Write local connection file for EG
          8. Return self
        """
        env = kwargs.get("env", {}) or {}

        job_id = env.get("COMPASSX_JOB_ID")
        if not job_id:
            raise RuntimeError(
                "COMPASSX_JOB_ID is required. Select a compute pod in the notebook toolbar."
            )

        pod = self._get_pod(job_id)
        pod_name = pod.metadata.name
        pod_ip = pod.status.pod_ip

        conn_file = f"{eg_settings.EG_CONNECTION_FILE_PATH}/kernel-{self.kernel_id}.json"

        command = [
            "python", "-m", "ipykernel_launcher",
            "--ip=0.0.0.0",
            "-f", conn_file,
        ]
        logger.info("Execing ipykernel into pod %s kernel_id=%s", pod_name, self.kernel_id)

        # Launch ipykernel in background — do not wait
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._exec_in_pod_background, pod_name, command)

        # Poll for connection file (up to timeout)
        timeout = eg_settings.EG_KERNEL_LAUNCH_TIMEOUT
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            await asyncio.sleep(0.5)
            try:
                result = self._exec_in_pod(pod_name, ["test", "-f", conn_file], timeout=5)
                # test -f returns empty stdout on success, non-zero exit raises
                break
            except RuntimeError:
                continue
        else:
            raise RuntimeError(
                f"Kernel failed to start in pod {pod_name} within {timeout}s. "
                "Check that ipykernel is installed in the pod image."
            )

        # Read connection file from pod
        stdout = self._exec_in_pod(pod_name, ["cat", conn_file])
        conn_info = json.loads(stdout)

        # Replace ip with pod IP so EG can reach the ZMQ ports
        conn_info["ip"] = pod_ip
        logger.info(
            "Kernel ready in pod %s at %s ports=%s",
            pod_name, pod_ip,
            {k: v for k, v in conn_info.items() if k.endswith("_port")},
        )

        # Write local connection file for EG
        local_path = f"/tmp/eg-kernel-{self.kernel_id}.json"
        with open(local_path, "w") as f:
            json.dump(conn_info, f)

        self.pod_name = pod_name
        self.pod_ip = pod_ip
        self.job_id = job_id
        self.local_conn = local_path

        return self

    async def poll(self) -> Optional[int]:
        """Return None if kernel alive, 1 if dead."""
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
            # K8s error — assume alive, let heartbeat detect true failure
            return None

    async def kill(self, restart: bool = False) -> None:
        """Kill the ipykernel process inside the pod. Does NOT delete the compute pod."""
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
            logger.warning("Could not kill kernel process in pod %s: %s", self.pod_name, exc)

        try:
            conn_path = f"{eg_settings.EG_CONNECTION_FILE_PATH}/kernel-{self.kernel_id}.json"
            self._exec_in_pod(self.pod_name, ["rm", "-f", conn_path], timeout=10)
        except Exception:
            pass

        if self.local_conn and os.path.exists(self.local_conn):
            try:
                os.remove(self.local_conn)
            except OSError:
                pass

        logger.info("Kernel %s killed in pod %s", self.kernel_id, self.pod_name)

    async def send_signal(self, signum: int) -> None:
        """Send signal to kernel process (e.g. SIGINT for interrupt)."""
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

    def _exec_in_pod(self, pod_name: str, command: list[str], timeout: int = 30) -> str:
        """Execute command in pod synchronously. Return stdout as string."""
        logger.debug("exec_in_pod pod=%s cmd=%s", pod_name, command)
        core = k8s_client.CoreV1Api()
        resp = k8s_stream.stream(
            core.connect_get_namespaced_pod_exec,
            pod_name,
            eg_settings.KERNEL_NAMESPACE,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _request_timeout=timeout,
        )
        if hasattr(resp, "read_all"):
            stdout = resp.read_all()
        else:
            stdout = resp if isinstance(resp, str) else ""

        return stdout

    def _exec_in_pod_background(self, pod_name: str, command: list[str]) -> None:
        """Fire-and-forget exec — used to launch ipykernel without blocking."""
        try:
            self._exec_in_pod(pod_name, command, timeout=eg_settings.EG_KERNEL_LAUNCH_TIMEOUT + 10)
        except Exception as exc:
            logger.debug("Background exec completed/errored (expected): %s", exc)

    def _get_pod(self, job_id: str) -> k8s_client.V1Pod:
        """Find compute pod by job_id label. Raises RuntimeError if not found or not Running."""
        core = k8s_client.CoreV1Api()
        try:
            pods = core.list_namespaced_pod(
                namespace=eg_settings.KERNEL_NAMESPACE,
                label_selector=f"{JOB_ID_LABEL}={job_id}",
            )
        except ApiException as exc:
            raise RuntimeError(f"K8s API error looking up pod for job {job_id}: {exc}") from exc

        if not pods.items:
            raise RuntimeError(
                f"Compute pod {job_id} not found. "
                "The pod may have stopped. Start a new compute pod and try again."
            )

        pod = pods.items[0]
        phase = pod.status.phase if pod.status and pod.status.phase else "Unknown"
        if phase != "Running":
            raise RuntimeError(
                f"Compute pod {job_id} is {phase}. "
                "Wait for it to be Running before connecting."
            )

        return pod
