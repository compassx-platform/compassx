"""Omnigent Dev Service — High-level orchestrator for dev sandboxes and Omnigent AI integration (SOLID / SRP / DIP)."""
import os
import re
import sys
import shutil
import logging
import subprocess
import difflib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from app.services.app_runner import app_runner_service, BASE_APPS_STORAGE
from app.services.drivers.factory import driver_factory
from app.services.ingress_service import ingress_service

logger = logging.getLogger(__name__)

# Active in-memory dev sessions
_DEV_SESSIONS: Dict[str, Dict[str, Any]] = {}


class OmnigentDevService:
    """Orchestrates interactive dev sessions and pair programming with Omnigent AI."""

    def get_repo_dir(self, app) -> str:
        """Get absolute path to local app repository."""
        app_dir = app_runner_service.get_app_dir(app.id)
        repo_dir = os.path.join(app_dir, "repo")
        if not os.path.exists(repo_dir):
            app_runner_service.clone_or_update_repo(app)
        return repo_dir

    def get_omnigent_server_url(self) -> str:
        """Return browser-accessible Omnigent server URL."""
        return ingress_service.get_omnigent_public_url()

    def get_omnigent_internal_url(self) -> str:
        """Return daemon-accessible internal Omnigent server URL."""
        return ingress_service.get_omnigent_internal_url()

    def check_omnigent_server(self) -> Dict[str, Any]:
        """Check connectivity to Databricks Omnigent server."""
        try:
            from services.omnigent.manager import get_omnigent_manager
            status = get_omnigent_manager().get_status()
            details = status.details or {}
            is_running = str(status.phase).lower() == "running" or details.get("ready", False)
            return {
                "available": is_running,
                "server_url": details.get("endpoint") or self.get_omnigent_server_url(),
                "version": details.get("version") or "Databricks Omnigent Server",
            }
        except Exception as exc:
            logger.debug("Error checking omnigent manager status: %s", exc)
            url = self.get_omnigent_server_url()
            return {"available": False, "server_url": url, "version": "Databricks Omnigent Server"}

    def get_llm_env_vars(self, workspace_id: Optional[str] = None) -> Dict[str, str]:
        """Extract active LLM credentials from CompassX catalog and system environment."""
        env_vars: Dict[str, str] = {}

        # 1. Standard host environment variables
        for key in [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DATABRICKS_HOST", "DATABRICKS_TOKEN",
            "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
            "DEEPSEEK_API_KEY", "XAI_API_KEY", "OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION"
        ]:
            val = os.getenv(key)
            if val:
                env_vars[key] = val

        # 2. Extract decrypted LLM credentials from CompassX database
        try:
            from app.database import AccountSessionLocal
            from app.models.agents import LLMConnection
            from app.services.encryption import decrypt_field

            with AccountSessionLocal() as db:
                query = db.query(LLMConnection)
                if workspace_id:
                    query = query.filter(LLMConnection.workspace_id == workspace_id)
                connections = query.all()

                for conn in connections:
                    key = decrypt_field(conn.api_key_enc) if conn.api_key_enc else ""
                    provider_str = str(conn.provider).lower()
                    if "azure" in provider_str:
                        if key and "AZURE_OPENAI_API_KEY" not in env_vars:
                            env_vars["AZURE_OPENAI_API_KEY"] = key
                            env_vars["OPENAI_API_KEY"] = key
                        if conn.base_url and "AZURE_OPENAI_ENDPOINT" not in env_vars:
                            env_vars["AZURE_OPENAI_ENDPOINT"] = conn.base_url
                            env_vars["OPENAI_BASE_URL"] = conn.base_url
                    elif "openai" in provider_str:
                        if key and "OPENAI_API_KEY" not in env_vars:
                            env_vars["OPENAI_API_KEY"] = key
                        if conn.base_url and "OPENAI_BASE_URL" not in env_vars:
                            env_vars["OPENAI_BASE_URL"] = conn.base_url
                    elif "anthropic" in provider_str:
                        if key and "ANTHROPIC_API_KEY" not in env_vars:
                            env_vars["ANTHROPIC_API_KEY"] = key
                    elif "databricks" in provider_str:
                        if key and "DATABRICKS_TOKEN" not in env_vars:
                            env_vars["DATABRICKS_TOKEN"] = key
                        if conn.base_url and "DATABRICKS_HOST" not in env_vars:
                            env_vars["DATABRICKS_HOST"] = conn.base_url
                    elif "gemini" in provider_str or "google" in provider_str:
                        if key and "GEMINI_API_KEY" not in env_vars:
                            env_vars["GEMINI_API_KEY"] = key
                            env_vars["GOOGLE_API_KEY"] = key
        except Exception as err:
            logger.warning("Could not load LLM credentials from database: %s", err)

        # 3. Add TLS / Certificate bypass variables
        env_vars.setdefault("NODE_TLS_REJECT_UNAUTHORIZED", "0")
        env_vars.setdefault("NPM_CONFIG_STRICT_SSL", "false")
        env_vars.setdefault("PYTHONHTTPSVERIFY", "0")
        env_vars.setdefault("GIT_SSL_NO_VERIFY", "true")
        env_vars.setdefault("CURL_INSECURE", "1")
        env_vars.setdefault("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")
        env_vars.setdefault("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
        env_vars.setdefault("NODE_EXTRA_CA_CERTS", "/etc/ssl/certs/ca-certificates.crt")
        env_vars.setdefault("CURL_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt")
        env_vars.setdefault(
            "OMNIGENT_RUNNER_ENV_PASSTHROUGH",
            "AZURE_OPENAI_API_KEY,AZURE_OPENAI_ENDPOINT,AZURE_OPENAI_API_VERSION,OPENAI_API_KEY,OPENAI_BASE_URL,NODE_TLS_REJECT_UNAUTHORIZED,NODE_EXTRA_CA_CERTS,SSL_CERT_FILE,REQUESTS_CA_BUNDLE,CURL_CA_BUNDLE,PYTHONHTTPSVERIFY,GIT_SSL_NO_VERIFY,CURL_INSECURE,NPM_CONFIG_STRICT_SSL"
        )

        return env_vars

    def ensure_omnigent_server(self) -> Dict[str, Any]:
        """Ensure Databricks Omnigent Server is running in Docker or Kubernetes on-demand."""
        try:
            from services.omnigent.manager import get_omnigent_manager
            mgr = get_omnigent_manager()
            status = mgr.get_status()
            is_running = str(status.phase).lower() == "running" or (status.details or {}).get("ready", False)
            if not is_running:
                status = mgr.start()
            details = status.details or {}
            is_running = str(status.phase).lower() == "running" or details.get("ready", False)
            return {
                "available": is_running,
                "server_url": details.get("endpoint") or self.get_omnigent_server_url(),
                "internal_url": details.get("internal_endpoint") or self.get_omnigent_internal_url(),
                "version": details.get("version") or "Databricks Omnigent Server",
            }
        except Exception as exc:
            logger.warning("Failed to ensure Omnigent server via manager: %s", exc)
            return self.check_omnigent_server()

    def get_app_host_identity(self, app) -> Tuple[str, str]:
        """Generate deterministic (host_id, host_name) for an app dev sandbox."""
        import uuid
        app_id = getattr(app, "id", str(app))
        app_name = getattr(app, "name", None) or getattr(app, "slug", None) or app_id
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{app_id}").hex
        host_name = str(app_name).strip()
        return host_id, host_name

    def create_or_get_omnigent_session(
        self, app, repo_dir: str, dev_port: int, host_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register or link the dev sandbox container to the shared Databricks Omnigent server."""
        server_status = self.ensure_omnigent_server()
        url = server_status.get("server_url") or self.get_omnigent_server_url()
        expected_host_id, expected_host_name = self.get_app_host_identity(app)

        if not server_status.get("available"):
            sess_id = f"sess_omnigent_{app.id}"
            return {
                "server_url": url,
                "server_connected": False,
                "session_id": sess_id,
                "session_url": ingress_service.get_omnigent_session_url(sess_id),
                "host_id": expected_host_id,
                "host_name": expected_host_name,
                "mode": "databricks_server",
            }

        import urllib.request
        import json
        try:
            # 1. If host_id not provided, try to find this app's online host
            if not host_id:
                try:
                    hosts_req = urllib.request.Request(f"{url}/v1/hosts", headers={"User-Agent": "CompassX/1.0"})
                    with urllib.request.urlopen(hosts_req, timeout=2.0) as resp:
                        hosts_data = json.loads(resp.read().decode())
                        for h in hosts_data.get("hosts", []):
                            if h.get("status") == "online":
                                if h.get("host_id") == expected_host_id or app.id in (h.get("name") or ""):
                                    host_id = h.get("host_id")
                                    break
                        if not host_id:
                            host_id = expected_host_id
                except Exception as h_err:
                    logger.warning("Could not list hosts from Omnigent server: %s", h_err)
                    host_id = expected_host_id

            # 2. Fetch available agents on Omnigent server
            agent_id = None
            try:
                agents_req = urllib.request.Request(f"{url}/v1/agents", headers={"User-Agent": "CompassX/1.0"})
                with urllib.request.urlopen(agents_req, timeout=2.0) as resp:
                    agents_data = json.loads(resp.read().decode())
                    data_list = agents_data.get("agents") or agents_data.get("data", [])
                    if data_list:
                        for preferred in ["polly", "opencode-native-ui", "codex-native-ui", "antigravity-native-ui"]:
                            for ag in data_list:
                                if ag.get("name") == preferred:
                                    agent_id = ag.get("id")
                                    break
                            if agent_id:
                                break
                        if not agent_id:
                            agent_id = data_list[0].get("id")
            except Exception as ag_err:
                logger.warning("Could not fetch agents list from Omnigent server: %s", ag_err)

            if not agent_id:
                agent_id = "057995d1517418e6839f51d340785dd6"

            # 3. Create session on Omnigent server
            payload_dict: Dict[str, Any] = {
                "title": f"Dev Sandbox: {app.name}",
                "agent_id": agent_id,
            }
            if host_id:
                payload_dict["host_id"] = host_id
                payload_dict["workspace"] = "/app"

            payload = json.dumps(payload_dict).encode("utf-8")
            session_id = None
            res_data: Dict[str, Any] = {}

            # Retry if host is still completing handshake
            for attempt in range(4):
                try:
                    req = urllib.request.Request(
                        f"{url}/v1/sessions",
                        data=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "CompassX/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=3.0) as resp:
                        res_data = json.loads(resp.read().decode())
                        session_id = res_data.get("id") or res_data.get("session_id")
                        break
                except urllib.error.HTTPError as he:
                    err_body = he.read().decode()
                    if "offline" in err_body.lower() and attempt < 2:
                        import time
                        time.sleep(1.0)
                        continue
                    elif "offline" in err_body.lower():
                        payload_dict.pop("host_id", None)
                        payload = json.dumps(payload_dict).encode("utf-8")
                        try:
                            req = urllib.request.Request(
                                f"{url}/v1/sessions",
                                data=payload,
                                headers={"Content-Type": "application/json", "User-Agent": "CompassX/1.0"},
                            )
                            with urllib.request.urlopen(req, timeout=3.0) as resp:
                                res_data = json.loads(resp.read().decode())
                                session_id = res_data.get("id") or res_data.get("session_id")
                                break
                        except Exception:
                            pass
                    logger.warning("Could not create remote session on Omnigent server (HTTP %s): %s", he.code, err_body)
                    break
                except Exception as e:
                    logger.warning("Could not create remote session on Omnigent server: %s", e)
                    break

            if not session_id:
                session_id = f"sess_omnigent_{app.id}"

            session_url = ingress_service.get_omnigent_session_url(session_id)

            return {
                "server_url": url,
                "server_connected": True,
                "session_id": session_id,
                "session_url": session_url,
                "host_id": host_id or expected_host_id,
                "host_name": expected_host_name,
                "host_online": bool(res_data.get("host_online") or host_id),
                "runner_online": bool(res_data.get("runner_online", True)),
                "workspace": res_data.get("workspace", "/app"),
                "mode": "databricks_server",
            }
        except Exception as e:
            logger.warning("Could not create remote session on Omnigent server: %s", e)
            sess_id = f"sess_omnigent_{app.id}"
            return {
                "server_url": url,
                "server_connected": True,
                "session_id": sess_id,
                "session_url": ingress_service.get_omnigent_session_url(sess_id),
                "host_id": host_id or expected_host_id,
                "host_name": expected_host_name,
                "host_online": True,
                "mode": "databricks_server",
            }

    def start_dev_session(self, app) -> Dict[str, Any]:
        """Start or retrieve the development sandbox using active runtime driver."""
        repo_dir = self.get_repo_dir(app)
        expected_host_id, expected_host_name = self.get_app_host_identity(app)

        # If already running in memory, return existing session
        if app.id in _DEV_SESSIONS:
            sess = _DEV_SESSIONS[app.id]
            dev_driver = driver_factory.get_dev_driver(sess.get("mode"))
            status = dev_driver.get_dev_status(app)
            if status.get("status") == "active":
                return sess

        # 1. Ensure Omnigent Server is up
        self.ensure_omnigent_server()
        omnigent_internal_url = self.get_omnigent_internal_url()

        # 2. Start dev sandbox via driver
        dev_driver = driver_factory.get_dev_driver()
        raw_driver_res = dev_driver.start_dev(app, repo_dir, omnigent_internal_url)

        dev_port = raw_driver_res.get("dev_port") or 9201
        dev_url = raw_driver_res.get("dev_url") or ingress_service.get_app_dev_url(app, dev_port)

        # 3. Create or link Omnigent session
        omnigent_link = self.create_or_get_omnigent_session(app, repo_dir, dev_port, host_id=expected_host_id)

        session_info = {
            "app_id": app.id,
            "app_identifier": f"compassx-app-{app.id}",
            "status": "active",
            "mode": raw_driver_res.get("mode", "docker"),
            "container_id": raw_driver_res.get("container_id"),
            "container_name": raw_driver_res.get("container_name"),
            "dev_port": dev_port,
            "dev_url": dev_url,
            "repo_dir": repo_dir,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "omnigent_attached": True,
            "omnigent_server_url": omnigent_link.get("server_url"),
            "omnigent_server_connected": omnigent_link.get("server_connected"),
            "omnigent_session_id": omnigent_link.get("session_id"),
            "omnigent_session_url": omnigent_link.get("session_url"),
            "host_id": omnigent_link.get("host_id") or expected_host_id,
            "host_name": expected_host_name,
            "host_online": omnigent_link.get("host_online", True),
            "workspace": omnigent_link.get("workspace", "/app"),
        }

        _DEV_SESSIONS[app.id] = session_info
        return session_info

    def get_dev_session(self, app) -> Dict[str, Any]:
        """Get current status of dev session and Omnigent server."""
        repo_dir = self.get_repo_dir(app)
        expected_host_id, expected_host_name = self.get_app_host_identity(app)
        server_status = self.check_omnigent_server()
        dev_driver = driver_factory.get_dev_driver()
        dev_status = dev_driver.get_dev_status(app)

        dev_url = ingress_service.get_app_dev_url(app, 9201)
        sess_id = f"sess_omnigent_{app.id}"
        session_url = ingress_service.get_omnigent_session_url(sess_id)

        if app.id in _DEV_SESSIONS:
            sess = _DEV_SESSIONS[app.id]
            sess["status"] = dev_status.get("status", "inactive")
            sess["omnigent_server_available"] = server_status.get("available", False)
            sess["omnigent_server_url"] = server_status.get("server_url") or self.get_omnigent_server_url()
            sess["omnigent_session_url"] = sess.get("omnigent_session_url") or session_url
            sess["phase"] = dev_status.get("phase")
            sess["pod_name"] = dev_status.get("pod_name")
            return sess

        return {
            "app_id": app.id,
            "status": dev_status.get("status", "inactive"),
            "dev_url": dev_url,
            "repo_dir": repo_dir,
            "omnigent_attached": dev_status.get("status") == "active",
            "omnigent_server_available": server_status.get("available", False),
            "omnigent_server_url": server_status.get("server_url") or self.get_omnigent_server_url(),
            "omnigent_session_url": session_url,
            "host_id": expected_host_id,
            "host_name": expected_host_name,
            "pod_name": dev_status.get("pod_name"),
            "phase": dev_status.get("phase"),
            "mode": dev_status.get("mode", "docker"),
        }

    def stop_dev_session(self, app) -> Dict[str, Any]:
        """Stop and clean up development sandbox."""
        sess = _DEV_SESSIONS.pop(app.id, None)
        mode = sess.get("mode") if sess else None
        dev_driver = driver_factory.get_dev_driver(mode)
        dev_driver.stop_dev(app)

        return {"status": "stopped", "app_id": app.id}

    def get_dev_logs(self, app, tail: int = 200) -> Dict[str, Any]:
        """Fetch runtime logs from dev sandbox."""
        sess = _DEV_SESSIONS.get(app.id)
        mode = sess.get("mode") if sess else None
        dev_driver = driver_factory.get_dev_driver(mode)
        logs = dev_driver.get_dev_logs(app)
        return {
            "app_id": app.id,
            "logs": logs or "Sandbox running. No output logged yet.",
            "status": "active" if sess else "inactive",
        }

    # ── Workspace File Operations ──────────────────────────────────────────

    def list_workspace_files(self, app) -> List[Dict[str, Any]]:
        """List files in the app workspace."""
        repo_dir = self.get_repo_dir(app)
        file_tree = []
        ignored = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", ".DS_Store"}

        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ignored]
            for file in files:
                if file in ignored:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_dir).replace("\\", "/")
                try:
                    size = os.path.getsize(full_path)
                except Exception:
                    size = 0
                file_tree.append({
                    "path": rel_path,
                    "name": file,
                    "size": size,
                    "ext": os.path.splitext(file)[1].lstrip("."),
                })

        return sorted(file_tree, key=lambda x: x["path"])

    def read_workspace_file(self, app, file_path: str) -> Dict[str, Any]:
        """Read text content of a workspace file."""
        repo_dir = self.get_repo_dir(app)
        safe_path = os.path.normpath(os.path.join(repo_dir, file_path.lstrip("/\\")))
        if not safe_path.startswith(repo_dir) or not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File '{file_path}' not found in app repository.")

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return {
            "path": file_path,
            "content": content,
            "size": len(content),
            "ext": os.path.splitext(file_path)[1].lstrip("."),
        }

    def write_workspace_file(self, app, file_path: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the workspace (triggering hot reload)."""
        repo_dir = self.get_repo_dir(app)
        safe_path = os.path.normpath(os.path.join(repo_dir, file_path.lstrip("/\\")))
        if not safe_path.startswith(repo_dir):
            raise ValueError("Invalid file path outside workspace root.")

        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        old_content = ""
        if os.path.exists(safe_path):
            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                old_content = f.read()

        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)

        diff = "".join(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))

        return {
            "path": file_path,
            "diff": diff,
            "saved": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Git Publish & Production Deployment ────────────────────────────────

    def publish_dev_changes(self, app, commit_message: str, user_id: str = "system") -> Dict[str, Any]:
        """Commit all modified files to Git, push to remote, and trigger clean production deployment."""
        repo_dir = self.get_repo_dir(app)

        # 1. Git commit & push
        subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, text=True, check=False)
        msg = commit_message.strip() or f"Omnigent Dev updates - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        commit_res = subprocess.run(["git", "commit", "-m", msg], cwd=repo_dir, capture_output=True, text=True, check=False)
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=repo_dir, capture_output=True, text=True, check=False)

        # 2. Stop dev container
        self.stop_dev_session(app)

        # 3. Trigger production deployment
        deploy_res = app_runner_service.deploy_app(app)

        return {
            "status": "published",
            "commit_message": msg,
            "commit_output": commit_res.stdout,
            "push_output": push_res.stdout,
            "production_runtime": deploy_res.get("runtime_info"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


omnigent_dev_service = OmnigentDevService()
