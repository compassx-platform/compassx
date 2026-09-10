"""Docker runtime drivers for Production Apps and Dev Sandboxes (SOLID / SRP)."""
import os
import re
import socket
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from app.services.drivers.base import BaseAppDriver, BaseDevDriver
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)


def find_free_tcp_port(start_port: int, max_port: int) -> int:
    """Find an available TCP port on localhost."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available free port found in range {start_port}-{max_port}")


def get_docker_network() -> str:
    """Detect available docker network."""
    try:
        net_check = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True, check=False)
        return "compassx_default" if "compassx_default" in net_check.stdout else "bridge"
    except Exception:
        return "bridge"


class DockerAppDriver(BaseAppDriver):
    """Manages containerized production applications running locally or in Docker Compose."""

    def is_available(self) -> bool:
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=2, check=False)
            return res.returncode == 0
        except Exception:
            return False

    def deploy(self, app, repo_dir: str, build_logs: List[str]) -> Dict[str, Any]:
        cfg = dict(app.config or {})
        runtime_meta = dict(cfg.get("runtime") or {})
        existing_port = runtime_meta.get("host_port")
        port = existing_port if (existing_port and isinstance(existing_port, int)) else find_free_tcp_port(9101, 9200)

        container_name = f"compassx-app-{app.id}"
        image_tag = f"compassx-app-{app.slug}:latest"
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # 1. Build image
        build_logs.append(f"[{now_ts}] [INFO] Building Docker container image: {image_tag}")
        build_res = subprocess.run(["docker", "build", "-t", image_tag, "."], cwd=repo_dir, capture_output=True, text=True, check=False)
        for line in (build_res.stdout or "").splitlines():
            if line.strip():
                build_logs.append(f"[{now_ts}] [BUILD] {line.strip()}")
        if build_res.returncode != 0:
            error_msg = build_res.stderr or "Docker build failed"
            build_logs.append(f"[{now_ts}] [ERROR] Docker build failed: {error_msg}")
            raise RuntimeError(f"Docker build failed: {error_msg}")

        # 2. Stop existing
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True, check=False)

        # 3. Build arguments
        env_args = [
            "-e", "PORT=8080",
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

        network = get_docker_network()
        run_cmd = ["docker", "run", "-d", "--name", container_name, "--network", network, "-p", f"{port}:8080"] + env_args + [image_tag]
        run_res = subprocess.run(run_cmd, capture_output=True, text=True, check=False)
        if run_res.returncode != 0:
            raise RuntimeError(f"Docker run failed: {run_res.stderr}")

        container_id = (run_res.stdout or "").strip()[:12]
        live_url = ingress_service.get_app_url(app, host_port=port)
        build_logs.append(f"[{now_ts}] [SUCCESS] Container running (ID: {container_id}) at {live_url}")

        return {
            "mode": "docker",
            "container_id": container_id,
            "container_name": container_name,
            "image_tag": image_tag,
            "host_port": port,
            "url": live_url,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

    def stop(self, app) -> bool:
        container_name = f"compassx-app-{app.id}"
        res = subprocess.run(["docker", "stop", container_name], capture_output=True, text=True, check=False)
        return res.returncode == 0

    def get_status(self, app) -> Dict[str, Any]:
        container_name = f"compassx-app-{app.id}"
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", container_name], capture_output=True, text=True, check=False)
        is_running = (res.stdout or "").strip().lower() == "running"
        return {"status": "running" if is_running else "stopped", "container_name": container_name}

    def get_logs(self, app, max_lines: int = 200) -> List[str]:
        container_name = f"compassx-app-{app.id}"
        res = subprocess.run(["docker", "logs", "--tail", str(max_lines), container_name], capture_output=True, text=True, check=False)
        output = (res.stdout or "") + (res.stderr or "")
        return [line for line in output.splitlines() if line.strip()]

    def get_live_url(self, app) -> str:
        cfg = dict(app.config or {})
        port = (cfg.get("runtime") or {}).get("host_port") or 8080
        return ingress_service.get_app_url(app, host_port=port)


class DockerDevDriver(BaseDevDriver):
    """Manages Docker-based interactive development sandboxes with Omnigent AI daemon."""

    def _image_exists(self, tag: str) -> bool:
        res = subprocess.run(["docker", "image", "inspect", tag], capture_output=True, text=True, check=False)
        return res.returncode == 0

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str) -> Dict[str, Any]:
        import uuid
        dev_container_name = f"compassx-app-dev-{app.id}"
        dev_port = find_free_tcp_port(9201, 9400)
        network = get_docker_network()

        # Stop existing dev container
        subprocess.run(["docker", "rm", "-f", dev_container_name], capture_output=True, text=True, check=False)

        # Host identity
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{app.id}").hex
        host_name = str(app.name or app.slug or app.id).strip()

        app_type = getattr(app, "app_type", "custom_web") or "custom_web"

        # Container boot script: writes config.yaml with app identity, configures TLS, starts FastAPI and React/Vite, then runs Omnigent host runner
        container_cmd = (
            f"mkdir -p /root/.omnigent && printf 'host:\\n  host_id: {host_id}\\n  name: \"{host_name}\"\\n' > /root/.omnigent/config.yaml; "
            f"export OMNIGENT_HOST_ID={host_id} OMNIGENT_HOST_NAME=\"{host_name}\" "
            f"CHOKIDAR_USEPOLLING=1 WATCHPACK_POLLING=true WATCHFILES_FORCE_POLLING=true "
            f"NODE_TLS_REJECT_UNAUTHORIZED=0 NPM_CONFIG_STRICT_SSL=false PYTHONHTTPSVERIFY=0 GIT_SSL_NO_VERIFY=true CURL_INSECURE=1; "
            f"(which opencode >/dev/null 2>&1 || npm install -g opencode-ai@1.18.0 || true); "
            f"mkdir -p /app && cd /app && "
            # 1. Detect and start Python FastAPI Backend in background (live reload on port 8000)
            f"BACKEND_DIR=\"\"; "
            f"if [ -d /app/backend ] && ( [ -f /app/backend/app.py ] || [ -f /app/backend/main.py ] || [ -f /app/backend/requirements.txt ] ); then BACKEND_DIR=\"/app/backend\"; "
            f"elif [ -d /app/api ] && ( [ -f /app/api/app.py ] || [ -f /app/api/main.py ] ); then BACKEND_DIR=\"/app/api\"; "
            f"elif [ -d /app/server ] && ( [ -f /app/server/app.py ] || [ -f /app/server/main.py ] ); then BACKEND_DIR=\"/app/server\"; "
            f"elif [ -f /app/app.py ] || [ -f /app/main.py ]; then BACKEND_DIR=\"/app\"; "
            f"fi; "
            f"if [ -n \"$BACKEND_DIR\" ]; then "
            f"  (cd \"$BACKEND_DIR\" && "
            f"   (if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi) && "
            f"   (pip install --no-cache-dir uvicorn fastapi || true) && "
            f"   if [ -f app.py ]; then "
            f"     (uvicorn app:app --host 0.0.0.0 --port 8000 --reload || python app.py) & "
            f"   elif [ -f main.py ]; then "
            f"     (uvicorn main:app --host 0.0.0.0 --port 8000 --reload || python main.py) & "
            f"   fi) & "
            f"fi; "
            # 2. Detect and start React / Vite Frontend in background (npm run dev on port 8080)
            f"FRONTEND_DIR=\"\"; "
            f"if [ -d /app/frontend ] && [ -f /app/frontend/package.json ]; then FRONTEND_DIR=\"/app/frontend\"; "
            f"elif [ -d /app/client ] && [ -f /app/client/package.json ]; then FRONTEND_DIR=\"/app/client\"; "
            f"elif [ -d /app/web ] && [ -f /app/web/package.json ]; then FRONTEND_DIR=\"/app/web\"; "
            f"elif [ -f /app/package.json ]; then FRONTEND_DIR=\"/app\"; "
            f"fi; "
            f"if [ -n \"$FRONTEND_DIR\" ]; then "
            f"  (cd \"$FRONTEND_DIR\" && "
            f"   (python3 -c \"import os, re\nfor f in ['vite.config.ts', 'vite.config.js']:\n if os.path.exists(f):\n  c = open(f, 'r').read()\n  if 'usePolling' not in c: c = re.sub(r'(server:\\s*\\{{)', r'\\\\1\\\\n    allowedHosts: true,\\\\n    watch: {{ usePolling: true, interval: 100 }},\\\\n    hmr: {{ clientPort: 443 }},', c)\n  c = c.replace('http://localhost:8080', 'http://localhost:8000')\n  c = c.replace('http://127.0.0.1:8085', 'http://localhost:8000')\n  open(f, 'w').write(c)\" 2>/dev/null || true) && "
            f"   (if [ ! -d node_modules ]; then npm install --prefer-offline --no-audit || npm install || true; fi) && "
            f"   (npx --yes vite --host 0.0.0.0 --port 8080 --cors || npm run dev -- --host 0.0.0.0 --port 8080 || npm start -- -p 8080 || npx --yes serve -l 8080 .)) & "
            f"elif [ -n \"$BACKEND_DIR\" ]; then "
            # Pure Python app (Streamlit or FastAPI on port 8080)
            f"  (cd \"$BACKEND_DIR\" && "
            f"   if grep -q 'streamlit' app.py 2>/dev/null || [ '{app_type}' = 'streamlit' ]; then "
            f"     pip install --no-cache-dir streamlit && exec streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true; "
            f"   elif [ -f app.py ]; then "
            f"     exec uvicorn app:app --host 0.0.0.0 --port 8080 --reload; "
            f"   elif [ -f main.py ]; then "
            f"     exec uvicorn main:app --host 0.0.0.0 --port 8080 --reload; "
            f"   fi) & "
            f"else "
            f"  if [ ! -f /app/index.html ]; then echo '<!DOCTYPE html><html><head><title>Dev Sandbox for {app.name}</title></head><body style=\"font-family:sans-serif;padding:2rem;\"><h1>Dev Sandbox for {app.name}</h1><p style=\"color:green;font-weight:bold;\">Connected to Omnigent Dev Studio</p></body></html>' > /app/index.html; fi; "
            f"  npx --yes serve -l 8080 /app & "
            f"fi; "
            f"omnigent host --server {omnigent_internal_url} --non-interactive"
        )

        dev_host_image = "compassx-dev-host:latest" if self._image_exists("compassx-dev-host:latest") else "ghcr.io/omnigent-ai/omnigent-host:latest"

        run_cmd = [
            "docker", "run", "-d",
            "--name", dev_container_name,
            "--hostname", f"compassx-app-{app.id}",
            "--network", network,
            "-p", f"{dev_port}:8080",
            "-v", f"{repo_dir}:/app",
            "-w", "/app",
            "-e", "PORT=8080",
            "-e", "DEV_MODE=true",
            "-e", f"APP_NAME={app.name}",
            "-e", f"APP_ID={app.id}",
            "-e", f"OMNIGENT_HOST_ID={host_id}",
            "-e", f"OMNIGENT_HOST_NAME={host_name}",
            "-e", f"HOST_ID={host_id}",
            "-e", f"HOST_NAME={host_name}",
            "-e", f"OMNIGENT_SERVER_URL={omnigent_internal_url}",
            dev_host_image,
            "bash", "-c", container_cmd
        ]

        run_res = subprocess.run(run_cmd, capture_output=True, text=True, check=False)
        if run_res.returncode != 0:
            raise RuntimeError(f"Failed to start dev container: {run_res.stderr}")

        container_id = (run_res.stdout or "").strip()[:12]
        dev_url = ingress_service.get_app_dev_url(app, dev_port=dev_port)

        return {
            "mode": "docker",
            "container_id": container_id,
            "container_name": dev_container_name,
            "dev_port": dev_port,
            "dev_url": dev_url,
            "host_id": host_id,
            "host_name": host_name,
            "status": "active",
        }

    def stop_dev(self, app) -> bool:
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "rm", "-f", dev_container_name], capture_output=True, text=True, check=False)
        return res.returncode == 0

    def get_dev_status(self, app) -> Dict[str, Any]:
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", dev_container_name], capture_output=True, text=True, check=False)
        state_status = (res.stdout or "").strip().lower()
        if state_status == "running":
            status = "active"
        elif state_status in ["removing", "restarting", "dead"]:
            status = "stopping"
        else:
            status = "stopped"
        return {"status": status, "container_name": dev_container_name}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app) -> str:
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "logs", "--tail", "250", dev_container_name], capture_output=True, text=True, check=False)
        return (res.stdout or "") + (res.stderr or "")
