"""Local process runtime drivers for host development fallback (SOLID / SRP)."""
import os
import sys
import uuid
import socket
import logging
import shutil
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
            "app_id": app.id,
            "mode": "local",
            "pid": proc.pid,
            "host_port": port,
            "url": live_url,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

    def start(self, app) -> Dict[str, Any]:
        repo_dir = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "apps", app.id, "repo")
        if os.path.exists(repo_dir):
            logs: List[str] = []
            res = self.deploy(app, repo_dir, logs)
            return {
                "app_id": app.id,
                "status": "starting",
                "phase": "Starting",
                "mode": "local",
                "step": 3,
                "step_description": "Starting local app process...",
                "message": "Starting local process...",
                "url": res.get("url", self.get_live_url(app)),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "app_id": app.id,
            "status": "starting",
            "phase": "Starting",
            "mode": "local",
            "step": 3,
            "step_description": "Starting local app process...",
            "message": "Starting local process...",
            "url": self.get_live_url(app),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def stop(self, app) -> bool:
        proc = _LOCAL_PROCESSES.pop(app.id, None)
        if proc:
            proc.terminate()
            return True
        return False

    def get_status(self, app) -> Dict[str, Any]:
        proc = _LOCAL_PROCESSES.get(app.id)
        now_iso = datetime.now(timezone.utc).isoformat()
        if proc and proc.poll() is None:
            return {
                "app_id": app.id,
                "status": "active",
                "phase": "Running",
                "mode": "local",
                "replicas": 1,
                "ready_replicas": 1,
                "available_replicas": 1,
                "step": 4,
                "step_description": "Local process running",
                "message": f"Local process running (PID: {proc.pid}).",
                "url": self.get_live_url(app),
                "last_updated": now_iso,
            }
        return {
            "app_id": app.id,
            "status": "stopped",
            "phase": "Stopped",
            "mode": "local",
            "replicas": 0,
            "ready_replicas": 0,
            "available_replicas": 0,
            "step": 0,
            "step_description": "Local process stopped",
            "message": "Local process is not running.",
            "url": self.get_live_url(app),
            "last_updated": now_iso,
        }

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

    def start_dev(
        self,
        app,
        repo_dir: str,
        omnigent_internal_url: str,
        workspace_folder: str = "",
        workspace_branch: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{app.id}").hex
        host_name = str(app.name or app.slug or app.id).strip()
        dev_port = find_free_tcp_port(9201, 9400)
        dev_url = ingress_service.get_app_dev_url(app, dev_port=dev_port)

        return {
            "app_id": app.id,
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
        return {"app_id": app.id, "status": "active", "mode": "local"}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app, max_lines: int = 200) -> str:
        return "Local sandbox running."

    def _resolve_bash(self) -> Optional[str]:
        """Resolve a POSIX bash shell path on Windows (Git Bash / MSYS) or Unix."""
        if sys.platform == "win32":
            git_path = shutil.which("git")
            if git_path:
                git_root = os.path.dirname(os.path.dirname(git_path))
                for cand in [
                    os.path.join(git_root, "bin", "bash.exe"),
                    os.path.join(git_root, "usr", "bin", "bash.exe"),
                ]:
                    if os.path.exists(cand):
                        return cand
            for cand in [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
            ]:
                if os.path.exists(cand):
                    return cand
        bash_in_path = shutil.which("bash")
        if bash_in_path:
            return bash_in_path
        return None

    def _resolve_workdir(self, app, workspace_folder: str = "") -> str:
        """Find or create the active workspace or repo directory on the host."""
        app_dir = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "apps", app.id)
        candidates = []
        if workspace_folder:
            candidates.append(os.path.join(app_dir, "workspaces", workspace_folder))
            if "/" in workspace_folder:
                sub = workspace_folder.split("/", 1)[1]
                candidates.append(os.path.join(app_dir, "workspaces", sub))
        candidates.append(os.path.join(app_dir, "repo"))
        candidates.append(app_dir)

        for cand in candidates:
            if os.path.isdir(cand):
                return os.path.abspath(cand)
        fallback = candidates[0]
        os.makedirs(fallback, exist_ok=True)
        return os.path.abspath(fallback)

    def exec_git_in_workspace(
        self,
        app,
        workspace_folder: str,
        commit_message: str,
        branch: str,
        auth_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        workdir = self._resolve_workdir(app, workspace_folder)
        if not os.path.exists(workdir):
            return {"success": False, "error": f"Workspace directory not found: {workdir}"}

        try:
            git_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
            if auth_url:
                subprocess.run(["git", "-c", "credential.helper=", "remote", "set-url", "origin", auth_url], cwd=workdir, env=git_env, capture_output=True, text=True, check=False)
            subprocess.run(["git", "-c", "core.longpaths=true", "checkout", "-B", branch], cwd=workdir, env=git_env, capture_output=True, text=True, check=False)
            subprocess.run(["git", "-c", "core.longpaths=true", "add", "-A"], cwd=workdir, env=git_env, capture_output=True, text=True, check=False)
            subprocess.run(["git", "-c", "core.longpaths=true", "commit", "-m", commit_message], cwd=workdir, env=git_env, capture_output=True, text=True, check=False)
            push_res = subprocess.run(["git", "-c", "credential.helper=", "-c", "core.longpaths=true", "push", "-u", "origin", branch], cwd=workdir, env=git_env, capture_output=True, text=True, check=False)
            sha_res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=workdir, env=git_env, capture_output=True, text=True, check=False)

            is_success = push_res.returncode == 0
            return {
                "success": is_success,
                "output": (push_res.stdout or "") + (push_res.stderr or ""),
                "commit_sha": (sha_res.stdout or "").strip(),
                "branch": branch,
                "error": None if is_success else (push_res.stderr or "Git push failed"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def exec_command_in_dev(
        self,
        app,
        command: str,
        workspace_folder: str = "",
    ) -> Dict[str, Any]:
        workdir = self._resolve_workdir(app, workspace_folder)
        bash_path = self._resolve_bash()
        try:
            if bash_path:
                res = subprocess.run(
                    [bash_path, "-c", command],
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                res = subprocess.run(
                    command,
                    shell=True,
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "output": (res.stdout or "") + (res.stderr or ""),
                "workdir": workdir,
            }
        except Exception as e:
            return {"success": False, "exit_code": 1, "output": str(e), "workdir": workdir}

    def get_live_branch(self, app, workspace_folder: str = "") -> Optional[str]:
        workdir = self._resolve_workdir(app, workspace_folder)
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            branch = (res.stdout or "").strip()
            return branch if branch and branch != "HEAD" else None
        except Exception:
            return None
