"""Docker-backed Enterprise Gateway process proxy."""

from __future__ import annotations

import asyncio
import json
import os
import time

import docker

from compassx_process_proxy import CompassXProcessProxy

EG_KERNEL_LAUNCH_TIMEOUT = int(os.environ.get("EG_KERNEL_LAUNCH_TIMEOUT", "120"))


class DockerCompassXProcessProxy(CompassXProcessProxy):
    """Launch and manage kernels inside CompassX Docker runtimes."""

    def __init__(self, kernel_manager, proxy_config):
        super().__init__(kernel_manager, proxy_config)
        self._docker = docker.from_env()
        self.container = None
        self.container_ip = None

    def _find_container(self, runtime_id: str):
        containers = self._docker.containers.list(
            all=True,
            filters={"label": f"compassx/runtime-id={runtime_id}"},
        )
        if not containers:
            raise RuntimeError(f"Docker runtime not found: {runtime_id}")
        return containers[0]

    def _container_ip(self, container) -> str:
        container.reload()
        networks = (container.attrs.get("NetworkSettings") or {}).get("Networks") or {}
        for network in networks.values():
            if network.get("IPAddress"):
                return network["IPAddress"]
        raise RuntimeError(f"Docker runtime has no network address: {container.name}")

    def _exec_output(self, command: list[str]) -> str:
        result = self.container.exec_run(command, demux=False)
        output = result.output or b""
        return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else str(output)

    def _set_connection(self, conn_info: dict) -> None:
        conn_info["ip"] = self.container_ip
        km = self.kernel_manager
        km.ip = self.container_ip
        km.shell_port = conn_info["shell_port"]
        km.iopub_port = conn_info["iopub_port"]
        km.stdin_port = conn_info["stdin_port"]
        km.control_port = conn_info["control_port"]
        km.hb_port = conn_info["hb_port"]
        pod_key = conn_info.get("key", "")
        if pod_key and hasattr(km, "session"):
            km.session.key = pod_key.encode() if isinstance(pod_key, str) else pod_key
        with open(km.connection_file, "w") as fh:
            json.dump(conn_info, fh)

    async def launch_process(self, kernel_cmd: list, **kwargs):
        env = kwargs.get("env", {}) or {}
        job_id = env.get("KERNEL_COMPASSX_JOB_ID") or env.get("COMPASSX_JOB_ID")
        if not job_id:
            raise RuntimeError("KERNEL_COMPASSX_JOB_ID is required")

        self.container = self._find_container(job_id)
        self.container_ip = self._container_ip(self.container)
        conn_file = f"/tmp/kernel-{self.kernel_id}.json"
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

        exec_id = self._docker.api.exec_create(self.container.id, command)["Id"]
        self._docker.api.exec_start(exec_id, detach=True)

        conn_json = ""
        started = time.monotonic()
        while time.monotonic() - started < EG_KERNEL_LAUNCH_TIMEOUT:
            await asyncio.sleep(0.5)
            try:
                conn_json = self._exec_output(["sh", "-c", f"test -s {conn_file} && cat {conn_file}"])
                if conn_json.strip():
                    break
            except Exception:
                pass
        else:
            raise RuntimeError(
                f"Kernel failed to start in Docker runtime {job_id}. "
                "Ensure ipykernel is installed in the runtime image."
            )

        self._set_connection(json.loads(conn_json))
        self.pod_name = self.container.name
        self.pod_ip = self.container_ip
        self.job_id = job_id
        self.local_conn = self.kernel_manager.connection_file
        return self

    def poll(self):
        if not self.container:
            return 1
        try:
            script = (
                "import os; target="
                + repr(f"kernel-{self.kernel_id}.json")
                + "; print(any(target in open('/proc/'+p+'/cmdline','rb').read().decode(errors='ignore') "
                "for p in os.listdir('/proc') if p.isdigit()))"
            )
            return None if self._exec_output(["python", "-c", script]).strip() == "True" else 1
        except Exception:
            return 1

    def kill(self, restart: bool = False) -> None:
        if not self.container:
            return
        try:
            script = (
                "import os; target="
                + repr(f"kernel-{self.kernel_id}.json")
                + "; print(next((p for p in os.listdir('/proc') if p.isdigit() and "
                "target in open('/proc/'+p+'/cmdline','rb').read().decode(errors='ignore')), ''))"
            )
            pid = self._exec_output(["python", "-c", script]).strip()
            if pid:
                self._exec_output(["kill", "-9", pid])
            self._exec_output(["rm", "-f", f"/tmp/kernel-{self.kernel_id}.json"])
        except Exception:
            pass
        if self.local_conn and os.path.exists(self.local_conn):
            try:
                os.remove(self.local_conn)
            except OSError:
                pass

    def send_signal(self, signum: int) -> None:
        if not self.container:
            return
        try:
            script = (
                "import os; target="
                + repr(f"kernel-{self.kernel_id}.json")
                + "; print(next((p for p in os.listdir('/proc') if p.isdigit() and "
                "target in open('/proc/'+p+'/cmdline','rb').read().decode(errors='ignore')), ''))"
            )
            pid = self._exec_output(["python", "-c", script]).strip()
            if pid:
                self._exec_output(["kill", f"-{signum}", pid])
        except Exception:
            pass