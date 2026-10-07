"""Docker runtime drivers for Production Apps and Dev Sandboxes (SOLID / SRP)."""
import os
import re
import json
import base64
import socket
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from app.services.drivers.base import BaseAppDriver, BaseDevDriver
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)


def find_free_tcp_port(start_port: int, max_port: int) -> int:
    """Find an available TCP port on localhost that is not occupied or allocated by Docker."""
    used_docker_ports = set()
    try:
        ps_res = subprocess.run(["docker", "ps", "--format", "{{.Ports}}"], capture_output=True, text=True, check=False)
        if ps_res.returncode == 0:
            import re
            for m in re.finditer(r":(\d+)->", ps_res.stdout):
                used_docker_ports.add(int(m.group(1)))
    except Exception:
        pass

    for port in range(start_port, max_port):
        if port in used_docker_ports:
            continue
        # Test 1: check if anything is already listening on this port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                continue

        # Test 2: check if we can bind on localhost
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
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

    def start(self, app) -> Dict[str, Any]:
        container_name = f"compassx-app-{app.id}"
        # Check if container exists
        inspect_res = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", container_name], capture_output=True, text=True, check=False)
        if inspect_res.returncode != 0:
            # Container does not exist; redeploy
            from app.services.app_runner import app_runner_service
            deploy_res = app_runner_service.deploy_app(app, runner_mode="docker")
            return {
                "app_id": app.id,
                "status": "provisioning",
                "phase": "ContainerCreating",
                "mode": "docker",
                "step": 2,
                "step_description": "Creating and provisioning Docker container...",
                "container_name": container_name,
                "message": "Provisioning Docker container...",
                "url": self.get_live_url(app),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        subprocess.run(["docker", "start", container_name], capture_output=True, text=True, check=False)
        return {
            "app_id": app.id,
            "status": "starting",
            "phase": "Starting",
            "mode": "docker",
            "step": 3,
            "step_description": "Starting Docker container process...",
            "container_name": container_name,
            "message": "Starting Docker container...",
            "url": self.get_live_url(app),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def get_status(self, app) -> Dict[str, Any]:
        container_name = f"compassx-app-{app.id}"
        cfg = dict(app.config or {})
        port = (cfg.get("runtime") or {}).get("host_port")
        res = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}|{{.State.Running}}|{{.State.Restarting}}|{{.State.OOMKilled}}", container_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            return {
                "app_id": app.id,
                "status": "stopped",
                "phase": "NotFound",
                "mode": "docker",
                "container_name": container_name,
                "replicas": 0,
                "ready_replicas": 0,
                "step": 0,
                "step_description": "Container not created",
                "message": "Docker container not found or stopped.",
                "url": self.get_live_url(app),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        parts = (res.stdout or "").strip().split("|")
        raw_status = parts[0].lower() if len(parts) > 0 else "unknown"
        is_running = parts[1].lower() == "true" if len(parts) > 1 else False
        is_restarting = parts[2].lower() == "true" if len(parts) > 2 else False
        is_oom = parts[3].lower() == "true" if len(parts) > 3 else False

        if is_oom:
            return {
                "app_id": app.id,
                "status": "error",
                "phase": "OOMKilled",
                "mode": "docker",
                "container_name": container_name,
                "replicas": 1,
                "ready_replicas": 0,
                "step": 0,
                "step_description": "Out of memory error",
                "message": "Container was terminated due to memory limit (OOMKilled).",
                "url": self.get_live_url(app),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        if is_running:
            return {
                "app_id": app.id,
                "status": "active",
                "phase": "Running",
                "mode": "docker",
                "container_name": container_name,
                "replicas": 1,
                "ready_replicas": 1,
                "step": 4,
                "step_description": f"Container running on port {port or 8080}",
                "message": "Application is live and ready.",
                "url": self.get_live_url(app),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        if is_restarting or raw_status in ("created", "restarting"):
            return {
                "app_id": app.id,
                "status": "starting",
                "phase": "ContainerCreating",
                "mode": "docker",
                "container_name": container_name,
                "replicas": 1,
                "ready_replicas": 0,
                "step": 3,
                "step_description": "Container is starting...",
                "message": "Docker container is starting...",
                "url": self.get_live_url(app),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "app_id": app.id,
            "status": "stopped",
            "phase": "Stopped",
            "mode": "docker",
            "container_name": container_name,
            "replicas": 0,
            "ready_replicas": 0,
            "step": 0,
            "step_description": "Container is stopped",
            "message": "Docker container is stopped.",
            "url": self.get_live_url(app),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

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

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str, workspace_folder: str = "", workspace_branch: str = "", host_type: str = "compassx", **kwargs) -> Dict[str, Any]:
        import uuid
        dev_container_name = f"compassx-app-dev-{app.id}"
        # Stop existing dev container for this app first so its port is released
        subprocess.run(["docker", "rm", "-f", dev_container_name], capture_output=True, text=True, check=False)

        dev_port = find_free_tcp_port(9201, 9400)
        network = get_docker_network()

        # Host identity
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{app.id}").hex
        host_name = str(app.name or app.slug or app.id).strip()

        app_type = getattr(app, "app_type", "custom_web") or "custom_web"
        git_subdir = (getattr(app, "git_subdir", "") or "").strip("/\\")

        target_branch = workspace_branch
        if not target_branch and workspace_folder:
            target_branch = f"dev/{workspace_folder.split('/')[-1]}"
        if not target_branch:
            target_branch = "dev/default"

        # Container boot script: writes config.yaml with app identity, configures TLS, starts FastAPI and React/Vite, then runs Omnigent host runner
        container_cmd = (
            f"mkdir -p /root/.gemini/antigravity-cli && "
            # Background daemon: syncs any real agy OAuth tokens between /root/.gemini and session directories
            f"(while true; do "
            f"  if [ -f /root/.gemini/antigravity-cli/antigravity-oauth-token ] && [ ! -f /root/.gemini/oauth_creds.json ]; then "
            f"    cp -f /root/.gemini/antigravity-cli/antigravity-oauth-token /root/.gemini/oauth_creds.json 2>/dev/null || true; "
            f"  fi; "
            f"  for t in /root/.omnigent/antigravity-native/*/agy-home/.gemini/antigravity-cli/antigravity-oauth-token; do "
            f"    if [ -f \"$t\" ] && grep -q 'refresh_token' \"$t\" 2>/dev/null; then "
            f"      cp -f \"$t\" /root/.gemini/antigravity-cli/antigravity-oauth-token 2>/dev/null || true; "
            f"      cp -f \"$t\" /root/.gemini/oauth_creds.json 2>/dev/null || true; "
            f"    fi; "
            f"  done; "
            f"  sleep 3; "
            f"done) & "
            f"mkdir -p /root/.omnigent /root/.config/omnigent /root/.config/opencode /root/.opencode && "
            f"printf 'host:\\n  host_id: {host_id}\\n  name: \"{host_name}\"\\n' | tee /root/.omnigent/config.yaml /root/.config/omnigent/config.yaml /root/.config/opencode/config.yaml /root/.opencode/config.yaml >/dev/null; "
            f"export OMNIGENT_HOST_ID={host_id} OMNIGENT_HOST_NAME=\"{host_name}\" HOST_ID={host_id} HOST_NAME=\"{host_name}\" OPENCODE_HOST_ID={host_id} OPENCODE_HOST_NAME=\"{host_name}\" "
            f"POSTGRES_DSN=\"postgresql://postgres:postgres@postgres:5432/autonomic\" REDIS_URL=\"redis://redis:6379/0\" JWT_SECRET=\"dev-jwt-secret-change-me-for-production-use-min-32-chars\" "
            f"CHOKIDAR_USEPOLLING=1 CHOKIDAR_INTERVAL=2000 WATCHPACK_POLLING=true WATCHPACK_POLLING_INTERVAL=2000 WATCHFILES_FORCE_POLLING=true WATCHFILES_POLL_DELAY_MS=2000 "
            f"NODE_TLS_REJECT_UNAUTHORIZED=0 NPM_CONFIG_STRICT_SSL=false PYTHONHTTPSVERIFY=0 GIT_SSL_NO_VERIFY=true CURL_INSECURE=1; "
            f"(which agy >/dev/null 2>&1 || (curl -k -fsSL -o /tmp/agy.tar.gz 'https://github.com/google-antigravity/antigravity-cli/releases/download/1.0.10/agy_cli_linux_x64.tar.gz' 2>/dev/null && tar -xzf /tmp/agy.tar.gz -C /tmp antigravity 2>/dev/null && install -m 0755 /tmp/antigravity /usr/local/bin/agy 2>/dev/null && rm -f /tmp/agy.tar.gz /tmp/antigravity) || (curl -k -fsSL https://antigravity.google/install.sh | bash 2>/dev/null || true)); "
            f"(which agy >/dev/null 2>&1 && ln -sf /usr/local/bin/agy /usr/local/bin/antigravity || true); "
            f"(which opencode >/dev/null 2>&1 || npm install -g opencode-ai@1.18.0 || true); "
            f"mkdir -p /app && cd /app && "
            f"(git checkout -B '{target_branch}' 2>/dev/null || true); "
            # Sync AI Gateway MCP servers to all harness configs (Claude, OpenCode, Antigravity, Codex)
            f"(python3 -c '"
            f"import json, os, urllib.request, ssl; "
            f"ctx = ssl._create_unverified_context(); "
            f"api_url = \"https://135.13.180.167.nip.io/api/v1/ai-gateway/mcp/servers\"; "
            f"servers = []; "
            f"try:\n"
            f"  req = urllib.request.Request(api_url, headers={{\"User-Agent\": \"CompassX-Dev-Sandbox/1.0\"}});\n"
            f"  with urllib.request.urlopen(req, context=ctx, timeout=5) as r:\n"
            f"    servers = json.loads(r.read().decode())\n"
            f"except Exception:\n"
            f"  pass\n"
            f"mcp_uni = {{}}; mcp_oc = {{}}; mcp_cl = {{}}\n"
            f"for s in servers:\n"
            f"  if not s.get(\"is_enabled\", True): continue\n"
            f"  name = s.get(\"name\") or \"mcp_server\"\n"
            f"  endpoint = s.get(\"endpoint_url\"); cmd = s.get(\"command\")\n"
            f"  if endpoint:\n"
            f"    mcp_uni[name] = {{\"url\": endpoint, \"type\": \"sse\"}}\n"
            f"    mcp_oc[name] = {{\"type\": \"remote\", \"url\": endpoint}}\n"
            f"    mcp_cl[name] = {{\"type\": \"sse\", \"url\": endpoint}}\n"
            f"  elif cmd:\n"
            f"    p = cmd.split()\n"
            f"    mcp_uni[name] = {{\"command\": p[0], \"args\": p[1:] if len(p) > 1 else []}}\n"
            f"    mcp_oc[name] = {{\"type\": \"local\", \"command\": p}}\n"
            f"    mcp_cl[name] = {{\"command\": p[0], \"args\": p[1:] if len(p) > 1 else []}}\n"
            f"uni_doc = {{\"mcpServers\": mcp_uni}}\n"
            f"oc_doc = {{\n"
            f"  \"$schema\": \"https://opencode.ai/config.json\",\n"
            f"  \"provider\": {{\n"
            f"    \"compassx\": {{\n"
            f"      \"name\": \"CompassX AI Gateway\",\n"
            f"      \"type\": \"openai\",\n"
            f"      \"options\": {{\n"
            f"        \"baseURL\": \"http://host.docker.internal:8000/api/v1/ai-gateway/v1\",\n"
            f"        \"apiKey\": \"cx_gw_app_{app.id}\"\n"
            f"      }},\n"
            f"      \"models\": {{\n"
            f"        \"gpt-5.4-mini\": {{\"name\": \"gpt-5.4-mini\"}},\n"
            f"        \"gpt-5.6-sol\": {{\"name\": \"gpt-5.6-sol\"}}\n"
            f"      }}\n"
            f"    }}\n"
            f"  }},\n"
            f"  \"mcp\": mcp_oc\n"
            f"}}\n"
            f"for p in [\".mcp.json\", \"mcp.json\"]:\n"
            f"  with open(p, \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
            f"with open(\"opencode.json\", \"w\") as f: json.dump(oc_doc, f, indent=2)\n"
            f"os.makedirs(\"/root/.config/opencode\", exist_ok=True); os.makedirs(\"/root/.opencode\", exist_ok=True)\n"
            f"with open(\"/root/.config/opencode/opencode.json\", \"w\") as f: json.dump(oc_doc, f, indent=2)\n"
            f"with open(\"/root/.opencode/opencode.json\", \"w\") as f: json.dump(oc_doc, f, indent=2)\n"
            f"pi_doc = {{\n"
            f"  \"providers\": {{\n"
            f"    \"compassx\": {{\n"
            f"      \"baseUrl\": \"http://host.docker.internal:8000/api/v1/ai-gateway/v1\",\n"
            f"      \"apiKey\": \"cx_gw_app_{app.id}\",\n"
            f"      \"api\": \"openai-completions\",\n"
            f"      \"models\": [\n"
            f"        {{\"id\": \"gpt-5.4-mini\", \"name\": \"gpt-5.4-mini\", \"contextWindow\": 128000, \"maxTokens\": 8192}},\n"
            f"        {{\"id\": \"gpt-5.6-sol\", \"name\": \"gpt-5.6-sol\", \"contextWindow\": 128000, \"maxTokens\": 8192}}\n"
            f"      ]\n"
            f"    }}\n"
            f"  }}\n"
            f"}}\n"
            f"os.makedirs(\"/root/.pi/agent\", exist_ok=True)\n"
            f"with open(\"/root/.pi/agent/models.json\", \"w\") as f: json.dump(pi_doc, f, indent=2)\n"
            f"os.makedirs(\"/root/.gemini/antigravity-cli\", exist_ok=True)\n"
            f"with open(\"/root/.gemini/antigravity-cli/mcp.json\", \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
            f"os.makedirs(\".gemini\", exist_ok=True)\n"
            f"with open(\".gemini/settings.json\", \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
            f"cl_path = \"/root/.claude.json\"; cl_data = {{}}\n"
            f"if os.path.exists(cl_path):\n"
            f"  try:\n"
            f"    with open(cl_path, \"r\") as f: cl_data = json.load(f)\n"
            f"  except Exception: pass\n"
            f"cwd = os.getcwd()\n"
            f"cl_data.setdefault(\"projects\", {{}})\n"
            f"cl_data[\"projects\"].setdefault(cwd, {{}})\n"
            f"cl_data[\"projects\"][cwd][\"mcpServers\"] = mcp_cl\n"
            f"with open(cl_path, \"w\") as f: json.dump(cl_data, f, indent=2)\n"
            f"' 2>/dev/null || true) && "
            # 1. Resolve Project Root considering Source Code Path (git_subdir) or auto-detect
            f"ROOT_DIR=\"/app\"; "
            f"if [ -n \"{workspace_folder}\" ] && [ -d \"/workspaces/{workspace_folder}\" ]; then ROOT_DIR=\"/workspaces/{workspace_folder}\"; fi; "
            f"APP_SUBDIR=\"{git_subdir}\"; "
            f"BASE_DIR=\"$ROOT_DIR\"; "
            f"if [ -n \"$APP_SUBDIR\" ] && [ -d \"$ROOT_DIR/$APP_SUBDIR\" ]; then BASE_DIR=\"$ROOT_DIR/$APP_SUBDIR\"; "
            f"else "
            f"  for d in \"$ROOT_DIR\"/*; do "
            f"    if [ -d \"$d\" ] && ( [ -d \"$d/frontend\" ] || [ -d \"$d/backend\" ] || [ -f \"$d/package.json\" ] ); then BASE_DIR=\"$d\"; break; fi; "
            f"  done; "
            f"fi; "
            # 2. Detect and start Python FastAPI Backend in background (live reload on port 8000 or DASHBOARD_PORT)
            f"BACKEND_DIR=\"\"; "
            f"if [ -d \"$BASE_DIR/backend\" ] && ( [ -f \"$BASE_DIR/backend/app.py\" ] || [ -f \"$BASE_DIR/backend/main.py\" ] || [ -f \"$BASE_DIR/backend/requirements.txt\" ] ); then BACKEND_DIR=\"$BASE_DIR/backend\"; "
            f"elif [ -d \"$BASE_DIR/api\" ] && ( [ -f \"$BASE_DIR/api/app.py\" ] || [ -f \"$BASE_DIR/api/main.py\" ] ); then BACKEND_DIR=\"$BASE_DIR/api\"; "
            f"elif [ -d \"$BASE_DIR/server\" ] && ( [ -f \"$BASE_DIR/server/app.py\" ] || [ -f \"$BASE_DIR/server/main.py\" ] ); then BACKEND_DIR=\"$BASE_DIR/server\"; "
            f"elif [ -f \"$BASE_DIR/app.py\" ] || [ -f \"$BASE_DIR/main.py\" ]; then BACKEND_DIR=\"$BASE_DIR\"; "
            f"elif [ -d \"$ROOT_DIR/backend\" ] && ( [ -f \"$ROOT_DIR/backend/app.py\" ] || [ -f \"$ROOT_DIR/backend/main.py\" ] || [ -f \"$ROOT_DIR/backend/requirements.txt\" ] ); then BACKEND_DIR=\"$ROOT_DIR/backend\"; "
            f"elif [ -d \"$ROOT_DIR/api\" ] && ( [ -f \"$ROOT_DIR/api/app.py\" ] || [ -f \"$ROOT_DIR/api/main.py\" ] ); then BACKEND_DIR=\"$ROOT_DIR/api\"; "
            f"elif [ -d \"$ROOT_DIR/server\" ] && ( [ -f \"$ROOT_DIR/server/app.py\" ] || [ -f \"$ROOT_DIR/server/main.py\" ] ); then BACKEND_DIR=\"$ROOT_DIR/server\"; "
            f"elif [ -f \"$ROOT_DIR/app.py\" ] || [ -f \"$ROOT_DIR/main.py\" ]; then BACKEND_DIR=\"$ROOT_DIR\"; "
            f"fi; "
            f"if [ -n \"$BACKEND_DIR\" ]; then "
            f"  (cd \"$BACKEND_DIR\" && "
            f"   export DASHBOARD_PORT=8000 PORT=8000 POSTGRES_DSN=\"postgresql://postgres:postgres@postgres:5432/autonomic\" REDIS_URL=\"redis://redis:6379/0\" JWT_SECRET=\"dev-jwt-secret-change-me-for-production-use-min-32-chars\"; "
            f"   (if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi) && "
            f"   (pip install --no-cache-dir uvicorn fastapi asyncpg || true) && "
            f"   (python3 -c '\n"
            f"import os, asyncpg, asyncio, glob\n"
            f"async def init_schema():\n"
            f"    dsn = os.environ.get(\"POSTGRES_DSN\")\n"
            f"    if not dsn: return\n"
            f"    try:\n"
            f"        conn = await asyncpg.connect(dsn)\n"
            f"        has_events = await conn.fetchval(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = \\x27events\\x27)\")\n"
            f"        if not has_events:\n"
            f"            for p in glob.glob(\"/app/**/schema.sql\", recursive=True) + glob.glob(\"/workspaces/**/schema.sql\", recursive=True):\n"
            f"                try:\n"
            f"                    sql = open(p).read()\n"
            f"                    await conn.execute(sql)\n"
            f"                    break\n"
            f"                except Exception:\n"
            f"                    pass\n"
            f"        await conn.close()\n"
            f"    except Exception:\n"
            f"        pass\n"
            f"asyncio.run(init_schema())\n"
            f"' 2>/dev/null || true) && "
            f"   if [ -f app.py ]; then "
            f"     (while true; do uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**' || python app.py || true; sleep 2; done) & "
            f"   elif [ -f main.py ]; then "
            f"     (while true; do uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**' || python main.py || true; sleep 2; done) & "
            f"   fi) & "
            f"fi; "
            # 3. Detect and start React / Vite Frontend in background (npm run dev on port 8080)
            f"FRONTEND_DIR=\"\"; "
            f"if [ -d \"$BASE_DIR/frontend\" ] && [ -f \"$BASE_DIR/frontend/package.json\" ]; then FRONTEND_DIR=\"$BASE_DIR/frontend\"; "
            f"elif [ -d \"$BASE_DIR/client\" ] && [ -f \"$BASE_DIR/client/package.json\" ]; then FRONTEND_DIR=\"$BASE_DIR/client\"; "
            f"elif [ -d \"$BASE_DIR/web\" ] && [ -f \"$BASE_DIR/web/package.json\" ]; then FRONTEND_DIR=\"$BASE_DIR/web\"; "
            f"elif [ -f \"$BASE_DIR/package.json\" ]; then FRONTEND_DIR=\"$BASE_DIR\"; "
            f"elif [ -d \"$ROOT_DIR/frontend\" ] && [ -f \"$ROOT_DIR/frontend/package.json\" ]; then FRONTEND_DIR=\"$ROOT_DIR/frontend\"; "
            f"elif [ -d \"$ROOT_DIR/client\" ] && [ -f \"$ROOT_DIR/client/package.json\" ]; then FRONTEND_DIR=\"$ROOT_DIR/client\"; "
            f"elif [ -d \"$ROOT_DIR/web\" ] && [ -f \"$ROOT_DIR/web/package.json\" ]; then FRONTEND_DIR=\"$ROOT_DIR/web\"; "
            f"elif [ -f \"$ROOT_DIR/package.json\" ]; then FRONTEND_DIR=\"$ROOT_DIR\"; "
            f"fi; "
            f"if [ -n \"$FRONTEND_DIR\" ]; then "
            f"  (cd \"$FRONTEND_DIR\" && "
            f"   export DASHBOARD_PORT=8000 DASHBOARD_UI_PORT=8080; "
            f"   (python3 -c \"import os, re\\nfor f in ['vite.config.ts', 'vite.config.js']:\\n if os.path.exists(f):\\n  c = open(f, 'r').read()\\n  if 'usePolling' not in c: c = re.sub(r'(server:\\s*\\{{)', r'\\\\1\\\\n    allowedHosts: true,\\\\n    watch: {{ usePolling: true, interval: 2000, ignored: [\\\\\"**/node_modules/**\\\\\", \\\\\"**/.git/**\\\\\", \\\\\"**/dist/**\\\\\", \\\\\"**/.cache/**\\\\\\\"] }},\\\\n    hmr: {{ clientPort: 443 }},', c)\\n  else: c = re.sub(r'watch:\\s*\\{{[^}}]*\\}}', 'watch: {{ usePolling: true, interval: 2000, ignored: [\\\\\"**/node_modules/**\\\\\", \\\\\"**/.git/**\\\\\", \\\\\"**/dist/**\\\\\", \\\\\"**/.cache/**\\\\\\\"] }}', c)\\n  c = c.replace('http://localhost:8080', 'http://localhost:8000')\\n  c = c.replace('http://127.0.0.1:8085', 'http://localhost:8000')\\n  open(f, 'w').write(c)\" 2>/dev/null || true) && "
            f"   (if [ ! -d node_modules ]; then npm install --prefer-offline --no-audit || npm install || true; fi) && "
            f"   (while true; do npx --yes vite --host 0.0.0.0 --port 8080 --cors || npm run dev -- --host 0.0.0.0 --port 8080 || npm start -- -p 8080 || npx --yes serve -l 8080 . || true; sleep 2; done)) & "
            f"elif [ -n \"$BACKEND_DIR\" ]; then "
            # Pure Python app (Streamlit or FastAPI on port 8080)
            f"  (cd \"$BACKEND_DIR\" && "
            f"   if grep -q 'streamlit' app.py 2>/dev/null || [ '{app_type}' = 'streamlit' ]; then "
            f"     pip install --no-cache-dir streamlit && exec streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true; "
            f"   elif [ -f app.py ]; then "
            f"     exec uvicorn app:app --host 0.0.0.0 --port 8080 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**'; "
            f"   elif [ -f main.py ]; then "
            f"     exec uvicorn main:app --host 0.0.0.0 --port 8080 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**'; "
            f"   fi) & "
            f"else "
            f"  if [ ! -f /app/index.html ]; then echo '<!DOCTYPE html><html><head><title>Dev Sandbox for {app.name}</title></head><body style=\"font-family:sans-serif;padding:2rem;\"><h1>Dev Sandbox for {app.name}</h1><p style=\"color:green;font-weight:bold;\">Connected to Omnigent Dev Studio</p></body></html>' > /app/index.html; fi; "
            f"  npx --yes serve -l 8080 /app & "
            f"fi; "
            f"exec omnigent host --server {omnigent_internal_url} --non-interactive"
        )

        # Resolve dev host image based on host_type selection
        host_type = str(host_type or kwargs.get("host_type") or "compassx").lower()
        if host_type == "omnigent":
            dev_host_image = "ghcr.io/omnigent-ai/omnigent-host:latest"
        else:
            host_type = "compassx"
            if self._image_exists("compassx-host:latest"):
                dev_host_image = "compassx-host:latest"
            elif self._image_exists("compassx-dev-host:latest"):
                dev_host_image = "compassx-dev-host:latest"
            else:
                dev_host_image = "ghcr.io/omnigent-ai/omnigent-host:latest"

        run_cmd = [
            "docker", "run", "-d",
            "--name", dev_container_name,
            "--hostname", f"compassx-app-{app.id}",
            "--network", network,
            "--add-host=host.docker.internal:host-gateway",
            "-p", f"{dev_port}:8080",
            "-v", f"{repo_dir}:/app",
            "-w", "/app",
            "-e", "PORT=8080",
            "-e", "DEV_MODE=true",
            "-e", f"APP_NAME={app.name}",
            "-e", f"APP_ID={app.id}",
            "-e", "POSTGRES_DSN=postgresql://postgres:postgres@postgres:5432/autonomic",
            "-e", "REDIS_URL=redis://redis:6379/0",
            "-e", "JWT_SECRET=dev-jwt-secret-change-me-for-production-use-min-32-chars",
            "-e", "OPENAI_BASE_URL=http://host.docker.internal:8000/api/v1/ai-gateway/v1",
            "-e", f"OPENAI_API_KEY=cx_gw_app_{app.id}",
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

        # Immediately seed CA certificates, Antigravity OAuth tokens, OpenCode & Pi configs
        try:
            self.ensure_agent_configs(app)
        except Exception as seed_err:
            logger.debug("Initial container config seeding: %s", seed_err)

        return {
            "mode": "docker",
            "container_id": container_id,
            "container_name": dev_container_name,
            "dev_port": dev_port,
            "dev_url": dev_url,
            "host_id": host_id,
            "host_name": host_name,
            "host_type": host_type,
            "host_image": dev_host_image,
            "status": "active",
        }

    def stop_dev(self, app) -> bool:
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "rm", "-f", dev_container_name], capture_output=True, text=True, check=False)
        return res.returncode == 0

    def suspend_dev(self, app) -> bool:
        """Suspend dev container by stopping it."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "stop", dev_container_name], capture_output=True, text=True, check=False)
        return res.returncode == 0

    def resume_dev(self, app) -> bool:
        """Resume suspended dev container."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "start", dev_container_name], capture_output=True, text=True, check=False)
        return res.returncode == 0

    def list_running_dev_app_ids(self) -> List[str]:
        """List app IDs of all running dev containers."""
        try:
            res = subprocess.run(
                ["docker", "ps", "--filter", "name=compassx-app-dev-", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                return []
            app_ids: List[str] = []
            prefix = "compassx-app-dev-"
            for line in (res.stdout or "").splitlines():
                line = line.strip()
                if line.startswith(prefix):
                    app_id = line[len(prefix):]
                    if app_id:
                        app_ids.append(app_id)
            return app_ids
        except Exception as e:
            logger.debug("Failed listing running dev containers: %s", e)
            return []

    def restart_dev(self, app) -> bool:
        dev_container_name = f"compassx-app-dev-{app.id}"
        subprocess.run(["docker", "rm", "-f", dev_container_name], capture_output=True, text=True, check=False)
        return True

    def get_dev_status(self, app) -> Dict[str, Any]:
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}|{{.Config.Image}}", dev_container_name], capture_output=True, text=True, check=False)
        output = (res.stdout or "").strip()
        state_status = ""
        image_name = ""
        if "|" in output:
            state_status, image_name = output.split("|", 1)
            state_status = state_status.strip().lower()
            image_name = image_name.strip()
        else:
            state_status = output.lower()

        if state_status == "running":
            status = "active"
        elif state_status in ["removing", "restarting", "dead"]:
            status = "stopping"
        else:
            status = "stopped"

        host_type = "omnigent" if "omnigent-host" in image_name and "compassx" not in image_name else "compassx"

        return {
            "status": status,
            "mode": "docker",
            "container_name": dev_container_name,
            "host_type": host_type if status != "stopped" else None,
            "host_image": image_name if status != "stopped" else None,
        }

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app, max_lines: int = 250) -> str:
        dev_container_name = f"compassx-app-dev-{app.id}"
        res = subprocess.run(["docker", "logs", "--tail", str(max_lines), dev_container_name], capture_output=True, text=True, check=False)
        return (res.stdout or "") + (res.stderr or "")

    def exec_git_in_workspace(
        self,
        app,
        workspace_folder: str,
        commit_message: str,
        branch: str,
        auth_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute git operations in docker dev container."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else "/app"
        safe_msg = commit_message.replace('"', '\\"').replace("'", "\\'")
        remote_snippet = f"git remote set-url origin '{auth_url}' 2>/dev/null || true; " if auth_url else ""
        cmd = (
            f"cd {workdir} 2>/dev/null || cd /app; "
            f"export GIT_TERMINAL_PROMPT=0; "
            f"git config user.name 'CompassX Dev' && git config user.email 'dev@compassx.io' && "
            f"(git checkout -B '{branch}' 2>/dev/null || true) && "
            f"{remote_snippet}"
            f"git add -A && "
            f"(git commit -m \"{safe_msg}\" 2>/dev/null || true) && "
            f"git push -u origin '{branch}' 2>&1 && echo '__GIT_PUSH_SUCCESS__'"
        )
        res = subprocess.run(["docker", "exec", dev_container_name, "bash", "-c", cmd], capture_output=True, text=True, check=False)
        raw_output = ((res.stdout or "") + (res.stderr or "")).strip()
        is_success = (res.returncode == 0) and ("__GIT_PUSH_SUCCESS__" in raw_output)
        clean_output = raw_output.replace("__GIT_PUSH_SUCCESS__", "").strip()

        sha_res = subprocess.run(["docker", "exec", dev_container_name, "bash", "-c", f"cd {workdir} 2>/dev/null || cd /app; git rev-parse --short HEAD 2>/dev/null || echo ''"], capture_output=True, text=True, check=False)
        return {
            "success": is_success,
            "output": clean_output,
            "commit_sha": (sha_res.stdout or "").strip(),
            "branch": branch,
            "error": None if is_success else (clean_output or "Git push command failed"),
        }


    def exec_command_in_dev(
        self,
        app,
        command: str,
        workspace_folder: str = "",
    ) -> Dict[str, Any]:
        dev_container_name = f"compassx-app-dev-{app.id}"
        # Verify if workspace folder exists in container, otherwise default to /app
        target_ws = f"/workspaces/{workspace_folder}" if workspace_folder else ""
        workdir = "/app"
        if target_ws:
            chk = subprocess.run(
                ["docker", "exec", dev_container_name, "bash", "-c", f"test -d '{target_ws}' && echo 'EXISTS'"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if "EXISTS" in (chk.stdout or ""):
                workdir = target_ws
            elif "/" in workspace_folder:
                sub = workspace_folder.split("/", 1)[1]
                chk_sub = subprocess.run(
                    ["docker", "exec", dev_container_name, "bash", "-c", f"test -d '/workspaces/{sub}' && echo 'EXISTS'"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                if "EXISTS" in (chk_sub.stdout or ""):
                    workdir = f"/workspaces/{sub}"
                else:
                    subprocess.run(
                        ["docker", "exec", dev_container_name, "bash", "-c", f"mkdir -p '{target_ws}' 2>/dev/null || true"],
                        check=False,
                    )
                    workdir = target_ws
            else:
                subprocess.run(
                    ["docker", "exec", dev_container_name, "bash", "-c", f"mkdir -p '{target_ws}' 2>/dev/null || true"],
                    check=False,
                )
                workdir = target_ws

        res = subprocess.run(
            ["docker", "exec", "-w", workdir, dev_container_name, "bash", "-c", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return {
            "success": res.returncode == 0,
            "exit_code": res.returncode,
            "output": (res.stdout or "") + (res.stderr or ""),
            "workdir": workdir,
        }

    def get_live_branch(self, app, workspace_folder: str = "") -> Optional[str]:
        """Fetch active Git branch from inside the running Docker dev container."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else "/app"
        try:
            res = subprocess.run(
                ["docker", "exec", "-w", workdir, dev_container_name, "bash", "-c", "git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ''"],
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

    def ensure_agent_configs(self, app, active_model: Optional[str] = None) -> None:
        """Seed or update agent configuration files (OpenCode, Pi) and root CA certificates inside the dev container."""
        dev_container_name = f"compassx-app-dev-{app.id}"

        # 0. Ensure corporate / host root CA certificates are installed so Go (agy) and TLS work behind corporate proxies
        try:
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            ca_cert_file = os.path.join(backend_dir, "certs", "corporate_ca.crt")
            if os.path.isfile(ca_cert_file):
                subprocess.run(
                    ["docker", "cp", ca_cert_file, f"{dev_container_name}:/usr/local/share/ca-certificates/corporate_ca.crt"],
                    capture_output=True,
                    check=False,
                    timeout=5.0,
                )
                subprocess.run(
                    ["docker", "exec", dev_container_name, "update-ca-certificates"],
                    capture_output=True,
                    check=False,
                    timeout=5.0,
                )

            # Ensure Antigravity OAuth token persistence across containers and restarts
            token_storage_dir = os.path.join(backend_dir, "storage", "credentials", "antigravity")
            host_token_file = os.path.join(token_storage_dir, "antigravity-oauth-token")
            host_creds_file = os.path.join(token_storage_dir, "oauth_creds.json")
            os.makedirs(token_storage_dir, exist_ok=True)

            # Check if container has an active valid OAuth token
            chk = subprocess.run(
                ["docker", "exec", dev_container_name, "bash", "-c", "test -f /root/.gemini/antigravity-cli/antigravity-oauth-token && cat /root/.gemini/antigravity-cli/antigravity-oauth-token"],
                capture_output=True, text=True, check=False, timeout=3.0,
            )
            container_token_content = (chk.stdout or "").strip() if chk.returncode == 0 else ""

            if container_token_content and "refresh_token" in container_token_content and "auto-authenticated" not in container_token_content:
                # Container has genuine token; persist to host storage
                with open(host_token_file, "w", encoding="utf-8") as f:
                    f.write(container_token_content)
                with open(host_creds_file, "w", encoding="utf-8") as f:
                    f.write(container_token_content)
            elif os.path.isfile(host_token_file):
                # Container is missing or has stale token; seed from host storage
                subprocess.run(
                    ["docker", "exec", dev_container_name, "mkdir", "-p", "/root/.gemini/antigravity-cli"],
                    capture_output=True, check=False, timeout=3.0,
                )
                subprocess.run(
                    ["docker", "cp", host_token_file, f"{dev_container_name}:/root/.gemini/antigravity-cli/antigravity-oauth-token"],
                    capture_output=True, check=False, timeout=3.0,
                )
                subprocess.run(
                    ["docker", "cp", host_token_file, f"{dev_container_name}:/root/.gemini/oauth_creds.json"],
                    capture_output=True, check=False, timeout=3.0,
                )
                # Also propagate to any running omnigent antigravity session home directories
                subprocess.run(
                    ["docker", "exec", dev_container_name, "bash", "-c",
                     "for d in /root/.omnigent/antigravity-native/*/agy-home/.gemini; do "
                     "  if [ -d \"$d\" ]; then "
                     "    mkdir -p \"$d/antigravity-cli\"; "
                     "    cp -f /root/.gemini/antigravity-cli/antigravity-oauth-token \"$d/antigravity-cli/\" 2>/dev/null || true; "
                     "    cp -f /root/.gemini/oauth_creds.json \"$d/\" 2>/dev/null || true; "
                     "  fi; "
                     "done"],
                    capture_output=True, check=False, timeout=3.0,
                )
        except Exception:
            pass

        models = ["gpt-5.4-mini", "gpt-5.6-sol"]
        try:
            from app.database import AccountSessionLocal
            from app.ai_gateway.models.provider import AIModelEndpoint
            with AccountSessionLocal() as acc_db:
                ws_id = str(app.workspace_id) if getattr(app, "workspace_id", None) else None
                q = acc_db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)
                if ws_id:
                    q = q.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
                db_models = [ep.name for ep in q.all() if ep.name]
                if db_models:
                    models = db_models
        except Exception as e:
            logger.debug("Failed to query models for container seeding: %s", e)

        if active_model and active_model not in models:
            models.append(active_model)

        api_key = f"cx_gw_app_{app.id}"
        base_url = "http://host.docker.internal:8000/api/v1/ai-gateway/v1"
        oc_models = {m: {"name": m} for m in models}
        pi_models = [{"id": m, "name": m, "contextWindow": 128000, "maxTokens": 8192} for m in models]

        py_script = (
            "import json, os\n"
            f"api_key = {json.dumps(api_key)}\n"
            f"base_url = {json.dumps(base_url)}\n"
            f"oc_models = {json.dumps(oc_models)}\n"
            f"pi_models = {json.dumps(pi_models)}\n"
            "for p in ['/root/.config/opencode/opencode.json', '/root/.opencode/opencode.json', '/app/opencode.json']:\n"
            "    try:\n"
            "        os.makedirs(os.path.dirname(p), exist_ok=True)\n"
            "        doc = {'$schema': 'https://opencode.ai/config.json'}\n"
            "        if os.path.exists(p):\n"
            "            try:\n"
            "                with open(p, 'r') as f: doc = json.load(f)\n"
            "            except Exception: pass\n"
            "        doc.setdefault('provider', {})\n"
            "        doc['provider']['compassx'] = {'name': 'CompassX AI Gateway', 'type': 'openai', 'options': {'baseURL': base_url, 'apiKey': api_key}, 'models': oc_models}\n"
            "        with open(p, 'w') as f: json.dump(doc, f, indent=2)\n"
            "    except Exception:\n"
            "        pass\n"
            "try:\n"
            "    tmux_cfg = (\n"
            "        'set-option -g history-limit 50000\\n'\n"
            "        'set-option -sq extended-keys on\\n'\n"
            "        'set-option -sq extended-keys-format csi-u\\n'\n"
            "        'set-option -sq set-clipboard external\\n'\n"
            "        'set-option -g mouse on\\n'\n"
            "        'set-option -g focus-events on\\n'\n"
            "        'set-option -g escape-time 0\\n'\n"
            "        'set-option -g window-size latest\\n'\n"
            "        'set-option -g aggressive-resize on\\n'\n"
            "        'set-option -g default-terminal \"xterm-256color\"\\n'\n"
            "        'set-option -g prefix None\\n'\n"
            "        'set-option -g prefix2 None\\n'\n"
            "        'set-option -g status off\\n'\n"
            "        'bind-key -T root PPage if-shell -F \"#{alternate_on}\" \"send-keys PPage\" \"copy-mode -eu\"\\n'\n"
            "        'bind-key -T copy-mode WheelUpPane select-pane \\\\; send-keys -X -N 5 scroll-up\\n'\n"
            "        'bind-key -T copy-mode WheelDownPane select-pane \\\\; send-keys -X -N 5 scroll-down\\n'\n"
            "        'bind-key -T copy-mode-vi WheelUpPane select-pane \\\\; send-keys -X -N 5 scroll-up\\n'\n"
            "        'bind-key -T copy-mode-vi WheelDownPane select-pane \\\\; send-keys -X -N 5 scroll-down\\n'\n"
            "    )\n"
            "    with open('/root/.tmux.conf', 'w') as f:\n"
            "        f.write(tmux_cfg)\n"
            "    os.system('tmux source-file /root/.tmux.conf 2>/dev/null')\n"
            "except Exception:\n"
            "    pass\n"
            "try:\n"
            "    pi_p = '/root/.pi/agent/models.json'\n"
            "    os.makedirs(os.path.dirname(pi_p), exist_ok=True)\n"
            "    pi_doc = {'providers': {}}\n"
            "    if os.path.exists(pi_p):\n"
            "        try:\n"
            "            with open(pi_p, 'r') as f: pi_doc = json.load(f)\n"
            "        except Exception: pass\n"
            "    pi_doc.setdefault('providers', {})\n"
            "    pi_doc['providers']['compassx'] = {'baseUrl': base_url, 'apiKey': api_key, 'api': 'openai-completions', 'models': pi_models}\n"
            "    with open(pi_p, 'w') as f: json.dump(pi_doc, f, indent=2)\n"
            "except Exception:\n"
            "    pass\n"
        )
        try:
            subprocess.run(
                ["docker", "exec", dev_container_name, "python3", "-c", py_script],
                capture_output=True,
                text=True,
                check=False,
                timeout=5.0,
            )
        except Exception as e:
            logger.debug("Failed to seed agent configs in container %s: %s", dev_container_name, e)

    def open_terminal_ws_client(
        self,
        app,
        workspace_folder: str = "",
        cols: int = 80,
        rows: int = 24,
        agent: Optional[str] = None,
        session_name: Optional[str] = None,
        cli_cmd: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Start a subprocess for Docker interactive exec."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        # Ensure agent configuration files (opencode.json, models.json) are seeded with gateway auth and models
        self.ensure_agent_configs(app, active_model=model)

        target_ws = f"/workspaces/{workspace_folder}" if workspace_folder else "/app"
        workdir = "/app"
        try:
            chk = subprocess.run(
                ["docker", "exec", dev_container_name, "bash", "-c", f"if [ -d '{target_ws}' ]; then echo 'EXISTS'; elif [ -d '/current' ]; then echo 'CURRENT'; else echo 'APP'; fi"],
                capture_output=True, text=True, check=False, timeout=3.0,
            )
            out = (chk.stdout or "").strip()
            if out == "EXISTS":
                workdir = target_ws
            elif out == "CURRENT":
                workdir = "/current"
            else:
                workdir = "/app"
        except Exception:
            workdir = "/app"

        if not cli_cmd:
            if agent == "pi":
                cli_cmd = "pi --approve"
            elif agent == "opencode":
                cli_cmd = "opencode"
            elif agent in ("antigravity", "agy"):
                cli_cmd = "agy --dangerously-skip-permissions"
            elif agent in ("bash", "shell", "sh"):
                cli_cmd = "exec /bin/bash -l"

        try:
            if session_name and cli_cmd:
                # Persistent tmux session inside container: attaches if existing (-A -D detaches stale clients), creates if not
                clean_cmd = f"export OPENAI_BASE_URL=http://host.docker.internal:8000/api/v1/ai-gateway/v1 OPENAI_API_KEY=cx_gw_app_{app.id}; {cli_cmd}".replace("'", "'\\''")
                tmux_target = session_name.replace("'", "")
                py_pty_script = (
                    "import pty, os, sys, fcntl, termios, struct; "
                    f"cols = int(os.environ.get('COLUMNS', {cols})); "
                    f"rows = int(os.environ.get('LINES', {rows})); "
                    "pid, m = pty.fork(); "
                    "("
                    "    (os.system('tmux source-file /root/.tmux.conf 2>/dev/null'), "
                    f"    os.execlp('tmux', 'tmux', 'new-session', '-A', '-D', '-s', '{tmux_target}', '-c', '{workdir}', '{clean_cmd} || bash'))[1] if pid == 0 else ("
                    "        fcntl.ioctl(m, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0)), "
                    "        pty._copy(m, pty._read, pty._read), "
                    "        os.close(m), "
                    "        os.waitpid(pid, 0)"
                    "    )"
                    ")"
                )
                cmd = [
                    "docker", "exec", "-i", "-w", workdir,
                    "-e", f"COLUMNS={cols}", "-e", f"LINES={rows}",
                    "-e", "TERM=xterm-256color",
                    "-e", "OPENAI_BASE_URL=http://host.docker.internal:8000/api/v1/ai-gateway/v1",
                    "-e", f"OPENAI_API_KEY=cx_gw_app_{app.id}",
                    dev_container_name,
                    "python3", "-c", py_pty_script,
                ]
            elif cli_cmd:
                # Launch interactive agent CLI in a genuine POSIX pseudo-terminal (PTY) inside Linux container
                clean_cmd = f"export OPENAI_BASE_URL=http://host.docker.internal:8000/api/v1/ai-gateway/v1 OPENAI_API_KEY=cx_gw_app_{app.id}; {cli_cmd}".replace("'", "'\\''")
                py_pty_script = (
                    "import pty, os, sys, fcntl, termios, struct; "
                    "cols = int(os.environ.get('COLUMNS', 100)); "
                    "rows = int(os.environ.get('LINES', 30)); "
                    "pid, m = pty.fork(); "
                    "("
                    f"    os.execlp('bash', 'bash', '-c', '{clean_cmd} || bash') if pid == 0 else ("
                    "        fcntl.ioctl(m, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0)), "
                    "        pty._copy(m, pty._read, pty._read), "
                    "        os.close(m), "
                    "        os.waitpid(pid, 0)"
                    "    )"
                    ")"
                )
                cmd = [
                    "docker", "exec", "-i", "-w", workdir,
                    "-e", f"COLUMNS={cols}", "-e", f"LINES={rows}",
                    "-e", "TERM=xterm-256color",
                    "-e", "OPENAI_BASE_URL=http://host.docker.internal:8000/api/v1/ai-gateway/v1",
                    "-e", f"OPENAI_API_KEY=cx_gw_app_{app.id}",
                    dev_container_name,
                    "python3", "-c", py_pty_script,
                ]
            else:
                cmd = [
                    "docker", "exec", "-i", "-w", workdir,
                    "-e", f"COLUMNS={cols}", "-e", f"LINES={rows}",
                    "-e", "TERM=xterm-256color",
                    "-e", "OPENAI_BASE_URL=http://host.docker.internal:8000/api/v1/ai-gateway/v1",
                    "-e", f"OPENAI_API_KEY=cx_gw_app_{app.id}",
                    dev_container_name,
                    "bash", "-l",
                ]

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            return proc
        except Exception as exc:
            logger.warning("Failed to start docker interactive terminal: %s", exc)
            return None

    def resize_terminal(
        self,
        app: Any,
        cols: int,
        rows: int,
        session_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Dynamically resize tmux window and attached client PTYs inside container."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        target = (session_name or "").replace("'", "")
        py_resize_script = (
            "import subprocess, fcntl, termios, struct, os\n"
            f"target = '{target}'\n"
            f"cols, rows = {int(cols)}, {int(rows)}\n"
            "try:\n"
            "    if target:\n"
            "        subprocess.run(['tmux', 'resize-window', '-t', target, '-x', str(cols), '-y', str(rows)], check=False, capture_output=True)\n"
            "        subprocess.run(['tmux', 'resize-pane', '-t', target, '-x', str(cols), '-y', str(rows)], check=False, capture_output=True)\n"
            "        p = subprocess.run(['tmux', 'list-clients', '-t', target, '-F', '#{client_tty}'], capture_output=True, text=True, check=False)\n"
            "    else:\n"
            "        subprocess.run(['tmux', 'resize-window', '-a', '-x', str(cols), '-y', str(rows)], check=False, capture_output=True)\n"
            "        p = subprocess.run(['tmux', 'list-clients', '-F', '#{client_tty}'], capture_output=True, text=True, check=False)\n"
            "    for tty in p.stdout.strip().splitlines():\n"
            "        t = tty.strip()\n"
            "        if t and os.path.exists(t):\n"
            "            try:\n"
            "                fd = os.open(t, os.O_RDWR)\n"
            "                fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))\n"
            "                os.close(fd)\n"
            "            except Exception:\n"
            "                pass\n"
            "except Exception:\n"
            "    pass\n"
        )
        try:
            subprocess.run(
                ["docker", "exec", dev_container_name, "python3", "-c", py_resize_script],
                capture_output=True,
                text=True,
                check=False,
                timeout=2.0,
            )
        except Exception as e:
            logger.debug("Failed to resize terminal in container %s: %s", dev_container_name, e)

    def create_git_worktree(
        self,
        app: Any,
        folder_path: str,
        branch: str,
        base_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new Git worktree sandbox inside the running dev container."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        clean_folder = folder_path.strip("/")
        target_dir = f"/workspaces/{clean_folder}"
        base = (base_branch or "main").strip() or "main"

        script = (
            f"mkdir -p /workspaces && "
            f"if [ -d '{target_dir}' ] && [ -e '{target_dir}/.git' ] && [ -n \"$(find '{target_dir}' -maxdepth 2 -not -name '.git*' -not -name 'index.html' 2>/dev/null)\" ]; then "
            f"  echo '__WORKTREE_EXISTS__'; "
            f"else "
            f"  BASE_REPO=\"\"; "
            f"  for d in /app /workspaces/*/default /workspaces/*/* /workspaces/*; do "
            f"    if [ -e \"$d/.git\" ] && [ \"$d\" != \"{target_dir}\" ] && [ -n \"$(ls -A \"$d\" 2>/dev/null)\" ]; then BASE_REPO=\"$d\"; break; fi; "
            f"  done; "
            f"  if [ -n \"$BASE_REPO\" ]; then "
            f"    (cd \"$BASE_REPO\" && git worktree prune 2>/dev/null || true); "
            f"    (cd \"$BASE_REPO\" && git fetch origin 2>/dev/null || true); "
            f"    rm -rf '{target_dir}'; "
            f"    if (cd \"$BASE_REPO\" && (git worktree add -f -B '{branch}' '{target_dir}' '{base}' 2>&1 || git worktree add -f -B '{branch}' '{target_dir}' 'origin/{base}' 2>&1 || git worktree add -f --detach '{target_dir}' '{base}' 2>&1 || git worktree add -f -B '{branch}' '{target_dir}' HEAD 2>&1)); then "
            f"      echo '__WORKTREE_CREATED__'; "
            f"    else "
            f"      mkdir -p '{target_dir}' && (git clone --shared \"$BASE_REPO\" '{target_dir}' 2>&1 || cp -a \"$BASE_REPO/.\" '{target_dir}/') && (cd '{target_dir}' && git checkout -B '{branch}' 2>/dev/null || true) && echo '__WORKTREE_CREATED__'; "
            f"    fi; "
            f"    for src_nm in \"$BASE_REPO/frontend/node_modules\" \"$BASE_REPO\"/*\"/frontend/node_modules\" \"$BASE_REPO/node_modules\" \"$BASE_REPO\"/*\"/node_modules\"; do "
            f"      if [ -d \"$src_nm\" ]; then "
            f"        rel_nm=\"${{src_nm#$BASE_REPO/}}\"; "
            f"        dest_dir=\"{target_dir}/${{rel_nm%/node_modules}}\"; "
            f"        if [ -d \"$dest_dir\" ] && [ ! -d \"$dest_dir/node_modules\" ]; then "
            f"          ln -sfn \"$src_nm\" \"$dest_dir/node_modules\" 2>/dev/null || true; "
            f"        fi; "
            f"      fi; "
            f"    done; "
            f"  else "
            f"    mkdir -p '{target_dir}' && echo '__WORKTREE_CREATED__'; "
            f"  fi; "
            f"fi"
        )
        res = subprocess.run(
            ["docker", "exec", dev_container_name, "bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )
        output = ((res.stdout or "") + (res.stderr or "")).strip()
        success = ("__WORKTREE_CREATED__" in output) or ("__WORKTREE_EXISTS__" in output)
        return {
            "success": success,
            "folder_path": target_dir,
            "branch": branch,
            "output": output,
            "error": None if success else (output or "Failed to create git worktree"),
        }

    def remove_git_worktree(
        self,
        app: Any,
        folder_path: str,
    ) -> bool:
        """Remove a Git worktree sandbox from the dev container."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        clean_folder = folder_path.strip("/")
        target_dir = f"/workspaces/{clean_folder}"
        script = (
            f"cd /app && git worktree remove --force '{target_dir}' 2>/dev/null || rm -rf '{target_dir}'; "
            f"cd /app && git worktree prune 2>/dev/null || true"
        )
        try:
            res = subprocess.run(
                ["docker", "exec", dev_container_name, "bash", "-c", script],
                capture_output=True,
                text=True,
                check=False,
                timeout=15.0,
            )
            return res.returncode == 0
        except Exception as e:
            logger.warning("Failed to remove git worktree %s: %s", target_dir, e)
            return False

    @staticmethod
    def _get_dev_runner_script() -> str:
        """Returns the unified dev runner bash supervisor script for development pods/containers."""
        from app.services.drivers.kubernetes_driver import KubernetesDevDriver
        return KubernetesDevDriver._get_dev_runner_script()

    def switch_active_sandbox(
        self,
        app: Any,
        folder_path: str,
    ) -> Dict[str, Any]:
        """Instantly switch active sandbox: repoint /current symlink and restart dev servers in target sandbox."""
        dev_container_name = f"compassx-app-dev-{app.id}"
        clean_folder = folder_path.strip("/")
        target_dir = f"/workspaces/{clean_folder}" if clean_folder else "/app"

        chk = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", dev_container_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if chk.returncode != 0 or chk.stdout.strip() != "true":
            return {"success": False, "error": f"Dev container {dev_container_name} is not running"}

        runner_script_b64 = base64.b64encode(self._get_dev_runner_script().encode("utf-8")).decode("ascii")
        switch_script = (
            f"echo '{runner_script_b64}' | base64 -d > /usr/local/bin/dev-runner.sh && "
            f"chmod +x /usr/local/bin/dev-runner.sh && "
            f"/usr/local/bin/dev-runner.sh reload '{target_dir}' && "
            f"echo '__SWITCH_SUCCESS__'"
        )
        res = subprocess.run(
            ["docker", "exec", dev_container_name, "bash", "-c", switch_script],
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )
        output = ((res.stdout or "") + (res.stderr or "")).strip()
        success = "__SWITCH_SUCCESS__" in output
        return {
            "success": success,
            "active_workdir": target_dir,
            "output": output,
            "error": None if success else (output or "Failed to switch active sandbox"),
        }


