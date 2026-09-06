import os
import sys
import shutil
import socket
import logging
import subprocess
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import httpx
from fastapi import Request, Response
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Base directory for app source code and runtime artifacts
BASE_APPS_STORAGE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage", "apps")
)

class AppRunnerService:
    """Manages multi-mode lifecycle (Docker / Local / Kubernetes) for deployed apps."""

    def __init__(self):
        os.makedirs(BASE_APPS_STORAGE, exist_ok=True)
        self._docker_available = None

    def is_docker_available(self) -> bool:
        """Check whether the local Docker daemon is reachable."""
        try:
            res = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def find_free_port(self, start_port: int = 9101, max_port: int = 9300) -> int:
        """Find an available TCP port on localhost."""
        for port in range(start_port, max_port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No available free port found in range 9101-9300")

    def get_app_dir(self, app_id: str) -> str:
        """Return workspace directory for a specific app."""
        app_dir = os.path.join(BASE_APPS_STORAGE, app_id)
        os.makedirs(app_dir, exist_ok=True)
        return app_dir

    def clone_or_update_repo(self, app) -> str:
        """Clone or pull the Git repository for the app."""
        app_dir = self.get_app_dir(app.id)
        repo_dir = os.path.join(app_dir, "repo")
        git_url = app.git_repo_url

        # Check for PAT auth
        git_token = None
        if hasattr(app, "git_pat_enc") and app.git_pat_enc:
            try:
                from app.services.encryption import decrypt_field
                git_token = decrypt_field(app.git_pat_enc)
            except Exception as e:
                logger.warning("Failed to decrypt app PAT: %s", e)

        auth_url = git_url
        if git_token and "github.com" in git_url and not ("@" in git_url.split("//")[-1]):
            # Insert token into clone url safely
            auth_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")

        git_ref = app.git_ref or app.git_branch or "main"

        if os.path.exists(os.path.join(repo_dir, ".git")):
            logger.info("Updating existing repo clone for app %s in %s", app.name, repo_dir)
            try:
                subprocess.run(["git", "fetch", "--all"], cwd=repo_dir, capture_output=True, text=True, check=True)
                subprocess.run(["git", "checkout", git_ref], cwd=repo_dir, capture_output=True, text=True, check=True)
                subprocess.run(["git", "pull"], cwd=repo_dir, capture_output=True, text=True, check=False)
            except Exception as e:
                logger.warning("Git pull failed for app %s, proceeding with current clone: %s", app.name, e)
        else:
            logger.info("Cloning repo %s (ref: %s) for app %s into %s", git_url, git_ref, app.name, repo_dir)
            if os.path.exists(repo_dir):
                shutil.rmtree(repo_dir, ignore_errors=True)
            res = subprocess.run(
                ["git", "clone", "--branch", git_ref, auth_url, repo_dir],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                # Retry with default clone if specific branch fails
                res2 = subprocess.run(
                    ["git", "clone", auth_url, repo_dir],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res2.returncode != 0:
                    raise RuntimeError(f"Git clone failed for {git_url}: {res.stderr or res2.stderr}")

        return repo_dir

    def ensure_dockerfile(self, repo_dir: str, app) -> None:
        """Generate a suitable Dockerfile if none exists in the repository."""
        dockerfile_path = os.path.join(repo_dir, "Dockerfile")
        if os.path.exists(dockerfile_path):
            return

        app_type = (app.app_type or "").lower()
        if "streamlit" in app_type:
            content = """FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi
RUN pip install --no-cache-dir streamlit
COPY . ./
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 CMD curl -f http://localhost:8080/_stcore/health || exit 1
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]
"""
        else:
            # Standard Python/FastAPI fallback
            content = """FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi
RUN pip install --no-cache-dir fastapi uvicorn[standard]
COPY . ./
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 CMD curl -f http://localhost:8080/api/health || exit 1
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
"""
        with open(dockerfile_path, "w", encoding="utf-8") as f:
            f.write(content)

    def deploy_app(self, app, runner_mode: Optional[str] = None) -> Dict[str, Any]:
        """Build and deploy the application in Docker or local runner."""
        repo_dir = self.clone_or_update_repo(app)
        self.ensure_dockerfile(repo_dir, app)

        use_docker = self.is_docker_available() if runner_mode is None else (runner_mode.lower() == "docker")

        # Determine host port
        cfg = dict(app.config or {})
        runtime_meta = dict(cfg.get("runtime") or {})
        existing_port = runtime_meta.get("host_port")

        port = existing_port if (existing_port and isinstance(existing_port, int)) else self.find_free_port()
        container_name = f"compassx-app-{app.id}"
        image_tag = f"compassx-app-{app.slug}:latest"
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        build_logs = [
            f"[{now_ts}] [INFO] Starting build for app '{app.name}' ({app.slug})",
            f"[{now_ts}] [INFO] Cloned Git repository from {app.git_repo_url} (ref: {app.git_ref or 'main'})",
            f"[{now_ts}] [INFO] Assigned local host port: {port}",
        ]

        if use_docker:
            # 1. Build Docker Image
            build_logs.append(f"[{now_ts}] [INFO] Building Docker container image: {image_tag}")
            build_res = subprocess.run(
                ["docker", "build", "-t", image_tag, "."],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            for line in (build_res.stdout or "").splitlines():
                if line.strip():
                    build_logs.append(f"[{now_ts}] [BUILD] {line.strip()}")
            if build_res.returncode != 0:
                error_msg = build_res.stderr or "Docker build failed"
                build_logs.append(f"[{now_ts}] [ERROR] Docker build failed: {error_msg}")
                raise RuntimeError(f"Docker build failed: {error_msg}")

            # 2. Stop & Remove any existing container
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True, check=False)

            # 3. Prepare Environment Variables
            env_args = [
                "-e", f"PORT=8080",
                "-e", f"APP_NAME={app.name}",
                "-e", f"APP_SLUG={app.slug}",
                "-e", f"APP_ID={app.id}",
                "-e", f"WORKSPACE_ID={app.workspace_id}",
            ]
            if app.workspace_identity:
                identity_id = app.workspace_identity.get("identity_id") or ""
                env_args.extend(["-e", f"COMPASSX_WORKLOAD_IDENTITY={identity_id}"])

            env_vars = cfg.get("env_vars") or []
            for ev in env_vars:
                if isinstance(ev, dict) and ev.get("key") and ev.get("value"):
                    env_args.extend(["-e", f"{ev['key']}={ev['value']}"])

            # 4. Run Docker Container
            build_logs.append(f"[{now_ts}] [INFO] Launching Docker container '{container_name}' on port {port}:8080...")
            run_cmd = ["docker", "run", "-d", "--name", container_name, "-p", f"{port}:8080"] + env_args + [image_tag]
            run_res = subprocess.run(run_cmd, capture_output=True, text=True, check=False)
            if run_res.returncode != 0:
                raise RuntimeError(f"Docker run failed: {run_res.stderr}")

            container_id = (run_res.stdout or "").strip()[:12]
            build_logs.append(f"[{now_ts}] [SUCCESS] Container running (ID: {container_id}) at http://localhost:{port}")

            runtime_info = {
                "mode": "docker",
                "container_id": container_id,
                "container_name": container_name,
                "image_tag": image_tag,
                "host_port": port,
                "url": f"http://localhost:{port}",
                "deployed_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
            }
        else:
            # Local Process Fallback
            build_logs.append(f"[{now_ts}] [INFO] Docker not detected. Spawning local app runner process on port {port}...")
            # For test app: start python backend directly
            backend_dir = os.path.join(repo_dir, "backend") if os.path.exists(os.path.join(repo_dir, "backend")) else repo_dir
            log_file = os.path.join(self.get_app_dir(app.id), "runtime.log")
            
            env = dict(os.environ)
            env["PORT"] = str(port)
            env["APP_ID"] = app.id

            with open(log_file, "a", encoding="utf-8") as f_out:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)],
                    cwd=backend_dir,
                    env=env,
                    stdout=f_out,
                    stderr=f_out,
                )

            build_logs.append(f"[{now_ts}] [SUCCESS] Process spawned (PID: {proc.pid}) at http://localhost:{port}")
            runtime_info = {
                "mode": "local",
                "pid": proc.pid,
                "host_port": port,
                "url": f"http://localhost:{port}",
                "log_file": log_file,
                "deployed_at": datetime.now(timezone.utc).isoformat(),
                "status": "running",
            }

        return {
            "runtime_info": runtime_info,
            "build_logs": build_logs,
        }

    def get_live_logs(self, app, tail: int = 250) -> List[str]:
        """Fetch actual runtime container or process logs."""
        cfg = app.config or {}
        runtime = cfg.get("runtime") or {}
        mode = runtime.get("mode", "docker")
        container_name = runtime.get("container_name") or f"compassx-app-{app.id}"

        if mode == "docker" and self.is_docker_available():
            res = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_name],
                capture_output=True,
                text=True,
                check=False,
            )
            raw = (res.stdout or "") + (res.stderr or "")
            lines = [l for l in raw.splitlines() if l.strip()]
            if lines:
                return lines

        # Local fallback log file
        log_file = runtime.get("log_file") or os.path.join(self.get_app_dir(app.id), "runtime.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    return [l.rstrip("\r\n") for l in all_lines[-tail:] if l.strip()]
            except Exception as e:
                logger.warning("Error reading runtime log file: %s", e)

        # Stored logs fallback
        return cfg.get("logs") or [f"[INFO] App container {container_name} is active."]

    def stop_app(self, app) -> None:
        """Stop the running container or process."""
        cfg = app.config or {}
        runtime = cfg.get("runtime") or {}
        mode = runtime.get("mode", "docker")
        container_name = runtime.get("container_name") or f"compassx-app-{app.id}"

        if mode == "docker" and self.is_docker_available():
            subprocess.run(["docker", "stop", container_name], capture_output=True, text=True, check=False)
        elif mode == "local":
            pid = runtime.get("pid")
            if pid:
                try:
                    import signal
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass

    def start_app(self, app) -> None:
        """Start a stopped container."""
        cfg = app.config or {}
        runtime = cfg.get("runtime") or {}
        mode = runtime.get("mode", "docker")
        container_name = runtime.get("container_name") or f"compassx-app-{app.id}"

        if mode == "docker" and self.is_docker_available():
            subprocess.run(["docker", "start", container_name], capture_output=True, text=True, check=False)

    def delete_app_runtime(self, app) -> None:
        """Completely clean up container and storage files."""
        cfg = app.config or {}
        runtime = cfg.get("runtime") or {}
        container_name = runtime.get("container_name") or f"compassx-app-{app.id}"

        if self.is_docker_available():
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True, check=False)

        app_dir = os.path.join(BASE_APPS_STORAGE, app.id)
        if os.path.exists(app_dir):
            shutil.rmtree(app_dir, ignore_errors=True)

    async def proxy_request(self, app, subpath: str, request: Request) -> Response:
        """Reverse-proxy HTTP requests to the running app container."""
        cfg = app.config or {}
        runtime = cfg.get("runtime") or {}
        port = runtime.get("host_port")
        if not port:
            raise RuntimeError("Application is not currently running on any allocated port.")

        target_url = f"http://127.0.0.1:{port}/{subpath.lstrip('/')}"
        if request.url.query:
            target_url += f"?{request.url.query}"

        client = httpx.AsyncClient(timeout=30.0)
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)

        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type"),
            )
        except Exception as e:
            logger.error("Error proxying to app %s on port %s: %s", app.name, port, e)
            return Response(
                content=f'{{"error": "Failed to proxy request to app container: {str(e)}"}}',
                status_code=502,
                media_type="application/json",
            )
        finally:
            await client.aclose()


app_runner_service = AppRunnerService()
