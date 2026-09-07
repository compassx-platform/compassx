"""App Runner Service — Orchestrates application lifecycles across Docker, Kubernetes, and Local runtimes (SOLID / SRP / DIP)."""
import os
import sys
import shutil
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import httpx
from fastapi import Request, Response

from app.services.drivers.factory import driver_factory
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)

# Base directory for app source code and runtime artifacts
BASE_APPS_STORAGE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "storage", "apps")
)


class AppRunnerService:
    """High-level application lifecycle orchestrator."""

    def __init__(self):
        os.makedirs(BASE_APPS_STORAGE, exist_ok=True)

    def is_docker_available(self) -> bool:
        """Check whether local Docker daemon is reachable."""
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=2, check=False)
            return res.returncode == 0
        except Exception:
            return False

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
        """Build and deploy the application using the active runtime driver."""
        repo_dir = self.clone_or_update_repo(app)
        self.ensure_dockerfile(repo_dir, app)

        driver = driver_factory.get_app_driver(runner_mode)
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        build_logs = [
            f"[{now_ts}] [INFO] Initiating deployment for app '{app.name}' ({app.slug})",
            f"[{now_ts}] [INFO] Active runtime driver: {driver.__class__.__name__}",
        ]

        runtime_info = driver.deploy(app, repo_dir, build_logs)

        return {
            "runtime_info": runtime_info,
            "build_logs": build_logs,
        }

    def get_live_logs(self, app, tail: int = 250) -> List[str]:
        """Fetch actual runtime container, pod, or process logs."""
        cfg = app.config or {}
        runtime = cfg.get("runtime") or {}
        mode = runtime.get("mode")

        driver = driver_factory.get_app_driver(mode)
        logs = driver.get_logs(app, max_lines=tail)
        if logs:
            return logs

        # Stored logs fallback
        return cfg.get("logs") or [f"[INFO] App '{app.name}' is registered and active."]

    def stop_app(self, app) -> None:
        """Stop the running container, pod, or process."""
        cfg = app.config or {}
        mode = (cfg.get("runtime") or {}).get("mode")
        driver = driver_factory.get_app_driver(mode)
        driver.stop(app)

    def start_app(self, app) -> None:
        """Start a stopped app instance."""
        cfg = app.config or {}
        mode = (cfg.get("runtime") or {}).get("mode")
        container_name = (cfg.get("runtime") or {}).get("container_name") or f"compassx-app-{app.id}"

        if (mode == "docker" or self.is_docker_available()) and container_name:
            subprocess.run(["docker", "start", container_name], capture_output=True, text=True, check=False)

    def delete_app_runtime(self, app) -> None:
        """Clean up app runtime resources and storage."""
        try:
            self.stop_app(app)
        except Exception:
            pass

        if self.is_docker_available():
            container_name = f"compassx-app-{app.id}"
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True, check=False)

        app_dir = os.path.join(BASE_APPS_STORAGE, app.id)
        if os.path.exists(app_dir):
            shutil.rmtree(app_dir, ignore_errors=True)

    async def proxy_request(self, app, subpath: str, request: Request) -> Response:
        """Reverse-proxy HTTP requests to the running app container when accessed locally."""
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
