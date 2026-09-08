"""Local process runtime drivers for host development fallback (SOLID / SRP)."""
import os
import sys
import uuid
import socket
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from app.services.drivers.base import BaseAppDriver, BaseDevDriver
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)

# Active background local processes
_LOCAL_PROCESSES: Dict[str, subprocess.Popen] = {}


def find_free_tcp_port(start_port: int, max_port: int) -> int:
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {start_port}-{max_port}")


class LocalAppDriver(BaseAppDriver):
    """Spawns native host processes for local testing when containers are unavailable."""

    def deploy(self, app, repo_dir: str, build_logs: List[str]) -> Dict[str, Any]:
        port = find_free_tcp_port(9101, 9200)
        backend_dir = os.path.join(repo_dir, "backend") if os.path.exists(os.path.join(repo_dir, "backend")) else repo_dir
        log_file = os.path.join(repo_dir, "..", "runtime.log")

        env = dict(os.environ)
        env["PORT"] = str(port)
        env["APP_ID"] = app.id

        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        build_logs.append(f"[{now_ts}] [INFO] Starting local process on port {port} in {backend_dir}")

        f_out = open(log_file, "a", encoding="utf-8")
        cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
        proc = subprocess.Popen(cmd, cwd=backend_dir, env=env, stdout=f_out, stderr=f_out)
        _LOCAL_PROCESSES[app.id] = proc

        live_url = ingress_service.get_app_url(app, host_port=port)
        build_logs.append(f"[{now_ts}] [SUCCESS] Local process active (PID: {proc.pid}) at {live_url}")

        return {
            "mode": "local",
            "pid": proc.pid,
            "host_port": port,
            "url": live_url,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

    def stop(self, app) -> bool:
        proc = _LOCAL_PROCESSES.pop(app.id, None)
        if proc:
            proc.terminate()
            return True
        return False

    def get_status(self, app) -> Dict[str, Any]:
        proc = _LOCAL_PROCESSES.get(app.id)
        if proc and proc.poll() is None:
            return {"status": "running", "pid": proc.pid}
        return {"status": "stopped"}

    def get_logs(self, app, max_lines: int = 200) -> List[str]:
        # Read from runtime log file
        log_file = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "apps", app.id, "runtime.log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                return [l.rstrip() for l in lines[-max_lines:]]
        return []

    def get_live_url(self, app) -> str:
        cfg = dict(app.config or {})
        port = (cfg.get("runtime") or {}).get("host_port") or 8080
        return ingress_service.get_app_url(app, host_port=port)


class LocalDevDriver(BaseDevDriver):
    """Manages local dev sandboxes."""

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str) -> Dict[str, Any]:
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{app.id}").hex
        host_name = str(app.name or app.slug or app.id).strip()
        dev_port = find_free_tcp_port(9201, 9400)
        dev_url = ingress_service.get_app_dev_url(app, dev_port=dev_port)

        return {
            "mode": "local",
            "dev_port": dev_port,
            "dev_url": dev_url,
            "host_id": host_id,
            "host_name": host_name,
            "status": "active",
        }

    def stop_dev(self, app) -> bool:
        return True

    def get_dev_status(self, app) -> Dict[str, Any]:
        return {"status": "active", "mode": "local"}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app) -> str:
        return "Local sandbox running."
