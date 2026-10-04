"""Omnigent Dev Service — High-level orchestrator for dev sandboxes and Omnigent AI integration (SOLID / SRP / DIP)."""
import os
import re
import sys
import shutil
import logging
import subprocess
import difflib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from app.services.app_runner import app_runner_service, BASE_APPS_STORAGE
from app.services.drivers.factory import driver_factory
from app.services.ingress_service import ingress_service
from app.services.app_manifest_service import app_manifest_service

logger = logging.getLogger(__name__)

# Active in-memory dev sessions
_DEV_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _get_system_db():
    """Get a system DB session for workspace operations."""
    from app.database import SystemSessionLocal
    return SystemSessionLocal()


def _clean_id(raw_id: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", raw_id.lower()).strip("-")


def _sanitize_workspace_name(raw_name: str) -> str:
    """Sanitize workspace name to be a clean, valid folder and identifier (lowercase alphanumeric, dashes, underscores)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", (raw_name or "").strip()).strip("-").lower()
    return cleaned or "default"



_OMNIGENT_SERVER_CACHE: Dict[str, Any] = {"data": None, "ts": 0}
_LIVE_HOST_CACHE: Dict[str, Any] = {}
_LAST_TOUCHED_WS: Dict[str, float] = {}


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
        """Check connectivity to Databricks Omnigent server (cached with 10s TTL)."""
        import time
        now = time.time()
        cached = _OMNIGENT_SERVER_CACHE.get("data")
        if cached and (now - _OMNIGENT_SERVER_CACHE.get("ts", 0)) < 10.0:
            return cached

        try:
            from services.omnigent.manager import get_omnigent_manager
            status = get_omnigent_manager().get_status()
            details = status.details or {}
            is_running = str(status.phase).lower() == "running" or details.get("ready", False)
            res = {
                "available": is_running,
                "server_url": details.get("endpoint") or self.get_omnigent_server_url(),
                "version": details.get("version") or "Databricks Omnigent Server",
            }
        except Exception as exc:
            logger.debug("Error checking omnigent manager status: %s", exc)
            url = self.get_omnigent_server_url()
            res = {"available": False, "server_url": url, "version": "Databricks Omnigent Server"}

        _OMNIGENT_SERVER_CACHE["data"] = res
        _OMNIGENT_SERVER_CACHE["ts"] = now
        return res

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

    def resolve_live_host(self, app, expected_host_id: Optional[str] = None) -> Tuple[str, str, bool]:
        """Query Omnigent Server /v1/hosts and dynamically match the live host for this app (cached with 10s TTL).
        Returns (host_id, host_name, is_online)."""
        import time
        import urllib.request
        import json

        app_id = getattr(app, "id", str(app))
        now = time.time()
        cached = _LIVE_HOST_CACHE.get(app_id)
        if cached and (now - cached.get("ts", 0)) < 10.0:
            return cached.get("result")

        default_host_id, default_host_name = self.get_app_host_identity(app)
        target_id = expected_host_id or default_host_id

        app_name = str(getattr(app, "name", "") or "").strip().lower()
        app_slug = str(getattr(app, "slug", "") or "").strip().lower()
        app_id_str = str(getattr(app, "id", "") or "").strip().lower()
        clean_id = _clean_id(app_id_str)

        match_targets = {app_name, app_slug, f"compassx-app-{app_id_str}", f"compassx-app-{clean_id}"}
        match_targets.discard("")

        urls = []
        int_url = self.get_omnigent_internal_url()
        pub_url = self.get_omnigent_server_url()
        if int_url:
            urls.append(int_url)
        if pub_url and pub_url not in urls:
            urls.append(pub_url)

        res = (target_id, default_host_name, False)
        for u in urls:
            try:
                hosts_req = urllib.request.Request(f"{u}/v1/hosts", headers={"User-Agent": "CompassX/1.0"})
                with urllib.request.urlopen(hosts_req, timeout=1.0) as resp:
                    hosts_data = json.loads(resp.read().decode())
                    hosts_list = hosts_data.get("hosts") or []

                    # 1. Exact ID match (online preferred)
                    for h in hosts_list:
                        h_id = h.get("host_id")
                        if h_id == target_id:
                            res = (h_id, h.get("name") or default_host_name, h.get("status") == "online")
                            break

                    # 2. Name / Slug match (online first)
                    if not res[2]:
                        for h in hosts_list:
                            h_name = str(h.get("name") or "").strip().lower()
                            if h_name in match_targets or (app_slug and app_slug in h_name) or (app_name and app_name in h_name):
                                if h.get("status") == "online":
                                    res = (h.get("host_id"), h.get("name") or default_host_name, True)
                                    break

                    # 3. Offline match by name / slug
                    if not res[2]:
                        for h in hosts_list:
                            h_name = str(h.get("name") or "").strip().lower()
                            if h_name in match_targets or (app_slug and app_slug in h_name) or (app_name and app_name in h_name):
                                res = (h.get("host_id"), h.get("name") or default_host_name, h.get("status") == "online")
                                break

                    break
            except Exception as e:
                logger.debug("Could not fetch hosts from %s: %s", u, e)

        _LIVE_HOST_CACHE[app_id] = {"result": res, "ts": now}
        return res

    def check_app_has_active_work(self, app, ws=None, cutoff_dt: Optional[datetime] = None) -> bool:
        """Multi-layer check to verify if app dev sandbox is actively being developed.
        Checks:
        1. Omnigent Server host status ('online') and active/recent sessions.
        2. Direct probe inside running dev pod / container for recent file edits (mtime).
        3. Local filesystem modification timestamps (mtime) in workspace folder.
        Returns True if active work is detected and refreshes ws.last_active_at in DB.
        """
        import urllib.request
        import json

        now = datetime.now(timezone.utc)
        if cutoff_dt is None:
            cutoff_dt = now - timedelta(seconds=7200)

        # ── 1. Check Omnigent Host & Sessions ─────────────────────────────────
        try:
            expected_host_id, _ = self.get_app_host_identity(app)
            host_id, host_name, is_online = self.resolve_live_host(app, expected_host_id)

            if is_online:
                # The dev runner is actively connected over WebSocket to Omnigent Server
                urls = []
                int_url = self.get_omnigent_internal_url()
                pub_url = self.get_omnigent_server_url()
                if int_url:
                    urls.append(int_url)
                if pub_url and pub_url not in urls:
                    urls.append(pub_url)

                cutoff_epoch = int(cutoff_dt.timestamp())
                for u in urls:
                    try:
                        req = urllib.request.Request(f"{u}/v1/sessions?limit=50", headers={"User-Agent": "CompassX/1.0"})
                        with urllib.request.urlopen(req, timeout=2.5) as resp:
                            data = json.loads(resp.read().decode())
                            sessions = data.get("sessions") or (data if isinstance(data, list) else [])
                            for s in sessions:
                                s_host = s.get("host_id")
                                s_ws = str(s.get("workspace") or "")
                                is_match = (
                                    (s_host and s_host == host_id)
                                    or (s_host and s_host == expected_host_id)
                                    or (ws and ws.folder_path and ws.folder_path in s_ws)
                                    or (getattr(app, "id", "") and getattr(app, "id", "") in s_ws)
                                    or (getattr(app, "slug", "") and getattr(app, "slug", "") in s_ws)
                                )
                                if is_match:
                                    status = str(s.get("status", "")).lower()
                                    updated_at = s.get("updated_at") or 0
                                    created_at = s.get("created_at") or 0
                                    if status in ["running", "active", "in_progress"] or updated_at >= cutoff_epoch or created_at >= cutoff_epoch:
                                        self.touch_workspace_activity(app.id, ws.id if ws else None)
                                        return True
                            break
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Error checking Omnigent live host/sessions: %s", e)

        # ── 2. Probe Inside Active Dev Pod / Container Workspace ──────────────
        try:
            dev_driver = driver_factory.get_dev_driver()
            ws_folder = ws.folder_path if (ws and ws.folder_path) else ""
            cutoff_mins = max(30, int((now - cutoff_dt).total_seconds() / 60))
            probe_cmd = (
                f"find . -maxdepth 4 "
                f"-not -path '*/.*' "
                f"-not -path '*/node_modules*' "
                f"-not -path '*/dist*' "
                f"-not -path '*/build*' "
                f"-not -path '*/.cache*' "
                f"-mmin -{cutoff_mins} -type f -print -quit"
            )
            res = dev_driver.exec_command_in_dev(app, command=probe_cmd, workspace_folder=ws_folder)
            if res.get("success") and res.get("output", "").strip():
                logger.info(
                    "Dev sandbox for app '%s' (%s) has recent file activity in pod (%s); keeping alive.",
                    app.name,
                    app.id,
                    res.get("output", "").strip()[:80],
                )
                self.touch_workspace_activity(app.id, ws.id if ws else None)
                return True
        except Exception as e:
            logger.debug("Error probing dev pod workspace directly: %s", e)

        # ── 3. Fallback: Check Local Filesystem mtime ─────────────────────────
        try:
            paths_to_check = []
            repo_dir = os.path.join(app_runner_service.get_app_dir(app.id), "repo")
            if os.path.exists(repo_dir):
                paths_to_check.append(repo_dir)

            if ws and ws.folder_path:
                ws_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws.folder_path.split("/")[-1])
                if os.path.exists(ws_dir):
                    paths_to_check.append(ws_dir)

            latest_mtime = 0.0
            ignore_dirs = {"node_modules", ".git", ".cache", "dist", "build", "__pycache__", ".venv"}

            for base_dir in paths_to_check:
                for root, dirs, files in os.walk(base_dir):
                    dirs[:] = [d for d in dirs if d not in ignore_dirs]
                    for f in files:
                        fp = os.path.join(root, f)
                        try:
                            mt = os.path.getmtime(fp)
                            if mt > latest_mtime:
                                latest_mtime = mt
                        except OSError:
                            continue

            if latest_mtime > 0:
                mtime_dt = datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
                if mtime_dt > cutoff_dt:
                    self.touch_workspace_activity(app.id, ws.id if ws else None)
                    return True
        except Exception as e:
            logger.debug("Error checking workspace filesystem mtime: %s", e)

        return False

    def create_or_get_omnigent_session(
        self,
        app,
        repo_dir: str,
        dev_port: int,
        host_id: Optional[str] = None,
        workspace_folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register or link the dev sandbox container to the shared Databricks Omnigent server."""
        server_status = self.ensure_omnigent_server()
        url = server_status.get("server_url") or self.get_omnigent_server_url()
        expected_host_id, expected_host_name = self.get_app_host_identity(app)

        # Dynamically resolve live host identity from Omnigent registry
        live_host_id, live_host_name, is_online = self.resolve_live_host(app, host_id or expected_host_id)
        if not host_id:
            host_id = live_host_id
            expected_host_name = live_host_name

        if not server_status.get("available"):
            sess_id = f"sess_omnigent_{app.id}"
            return {
                "server_url": url,
                "server_connected": False,
                "session_id": sess_id,
                "session_url": ingress_service.get_omnigent_session_url(sess_id),
                "host_id": host_id,
                "host_name": expected_host_name,
                "mode": "databricks_server",
            }

        import urllib.request
        import json
        try:

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
            ws_path = f"/workspaces/{workspace_folder}" if workspace_folder else "/workspaces"
            payload_dict: Dict[str, Any] = {
                "title": f"Dev Sandbox: {app.name}",
                "agent_id": agent_id,
            }
            if host_id:
                payload_dict["host_id"] = host_id
                payload_dict["workspace"] = ws_path

                # Proactively ensure directory exists on the live host
                try:
                    mkdir_payload = json.dumps({"path": ws_path}).encode("utf-8")
                    mkdir_req = urllib.request.Request(
                        f"{url}/v1/hosts/{host_id}/directories",
                        data=mkdir_payload,
                        headers={"Content-Type": "application/json", "User-Agent": "CompassX/1.0"},
                        method="POST",
                    )
                    with urllib.request.urlopen(mkdir_req, timeout=2.0) as _:
                        pass
                except Exception as mkdir_err:
                    logger.debug("Proactive host workspace directory ensure: %s", mkdir_err)

            payload = json.dumps(payload_dict).encode("utf-8")
            session_id = None
            res_data: Dict[str, Any] = {}

            # Retry if host is still completing handshake or creating path
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
                    if "does not exist" in err_body.lower() and host_id and ws_path and attempt < 2:
                        try:
                            mkdir_payload = json.dumps({"path": ws_path}).encode("utf-8")
                            mkdir_req = urllib.request.Request(
                                f"{url}/v1/hosts/{host_id}/directories",
                                data=mkdir_payload,
                                headers={"Content-Type": "application/json", "User-Agent": "CompassX/1.0"},
                                method="POST",
                            )
                            with urllib.request.urlopen(mkdir_req, timeout=2.0) as _:
                                pass
                            continue
                        except Exception:
                            pass
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
                "workspace": res_data.get("workspace", ws_path),
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
                "workspace": f"/workspaces/{workspace_folder}" if workspace_folder else "/workspaces",
                "mode": "databricks_server",
            }

    def start_dev_session(
        self,
        app,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
        host_type: str = "compassx",
    ) -> Dict[str, Any]:
        """Start or retrieve the development sandbox using active runtime driver."""
        repo_dir = self.get_repo_dir(app)
        expected_host_id, expected_host_name = self.get_app_host_identity(app)
        clean_app_id = _clean_id(app.id)

        # ── Resolve or create DevWorkspace record ──────────────────────────────
        from app.models.dev_workspace import DevWorkspace
        ws_record = None
        try:
            with _get_system_db() as db:
                if workspace_id:
                    ws_record = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                    ).first()

                if not ws_record and workspace_name:
                    clean_name = _sanitize_workspace_name(workspace_name)
                    ws_record = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.name == clean_name) | (DevWorkspace.id == clean_name[:32]),
                    ).first()

                if not ws_record:
                    # User specified name or auto-generate matching name & folder name
                    if workspace_name:
                        clean_name = _sanitize_workspace_name(workspace_name)
                    else:
                        ts = datetime.now(timezone.utc).strftime("%b%d-%H%M").lower()
                        clean_name = f"ws-{ts}"

                    folder_path = f"{clean_app_id}/{clean_name}"
                    branch = getattr(app, "git_branch", None) or f"dev/{clean_name}"
                    ws_id = clean_name[:32]

                    # Verify ID uniqueness across DB
                    id_conflict = db.query(DevWorkspace).filter(DevWorkspace.id == ws_id).first()
                    if id_conflict and id_conflict.app_id != app.id:
                        ws_id = f"{clean_name[:24]}_{uuid.uuid4().hex[:6]}"

                    # Set other workspaces for this app to inactive
                    db.query(DevWorkspace).filter(DevWorkspace.app_id == app.id).update({"status": "inactive"})

                    ws_record = DevWorkspace(
                        id=ws_id,
                        app_id=app.id,
                        workspace_id=getattr(app, "workspace_id", ""),
                        name=clean_name,
                        folder_path=folder_path,
                        git_branch=branch,
                        status="active",
                        created_by=None,
                        last_active_at=datetime.now(timezone.utc),
                    )
                    db.add(ws_record)
                    db.commit()
                    db.refresh(ws_record)
                else:
                    # Set other workspaces for this app to inactive
                    db.query(DevWorkspace).filter(DevWorkspace.app_id == app.id).update({"status": "inactive"})
                    ws_record.status = "active"
                    ws_record.last_active_at = datetime.now(timezone.utc)
                    db.commit()
                    db.refresh(ws_record)

                folder_path = ws_record.folder_path
                ws_id = ws_record.id
                ws_name = ws_record.name
                ws_branch = ws_record.git_branch or f"dev/{ws_name}"
        except Exception as ws_err:
            logger.warning("Could not manage DevWorkspace record: %s", ws_err)
            clean_name = _sanitize_workspace_name(workspace_name or f"ws-{datetime.now(timezone.utc).strftime('%b%d-%H%M').lower()}")
            ws_id = clean_name[:32]
            folder_path = f"{clean_app_id}/{clean_name}"
            ws_name = clean_name
            ws_branch = f"dev/{clean_name}"

        # If already running in memory for this workspace, return existing session
        session_key = f"{app.id}:{ws_id}"
        if session_key in _DEV_SESSIONS:
            sess = _DEV_SESSIONS[session_key]
            dev_driver = driver_factory.get_dev_driver(sess.get("mode"))
            status = dev_driver.get_dev_status(app)
            if status.get("status") == "active":
                return sess

        # 1. Ensure Omnigent Server is up
        self.ensure_omnigent_server()
        omnigent_internal_url = self.get_omnigent_internal_url()

        # 2. Start dev sandbox via driver (pass workspace folder, branch & host_type)
        dev_driver = driver_factory.get_dev_driver()
        raw_driver_res = dev_driver.start_dev(
            app, repo_dir, omnigent_internal_url, workspace_folder=folder_path, workspace_branch=ws_branch, host_type=host_type
        )

        dev_port = raw_driver_res.get("dev_port") or 9201
        dev_url = raw_driver_res.get("dev_url") or ingress_service.get_app_dev_url(app, dev_port)

        # 3. Create or link Omnigent session
        omnigent_link = self.create_or_get_omnigent_session(
            app, repo_dir, dev_port, host_id=expected_host_id, workspace_folder=folder_path
        )

        resolved_host_id = omnigent_link.get("host_id") or expected_host_id
        resolved_host_name = omnigent_link.get("host_name") or expected_host_name

        # 4. Synchronize AI Gateway MCP configs to local workspace / repo folder
        try:
            from app.ai_gateway.mcp.omnigent_sync import sync_workspace_mcp_configs
            sync_workspace_mcp_configs(repo_dir)
            ws_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
            if os.path.exists(ws_dir):
                sync_workspace_mcp_configs(ws_dir)
        except Exception as mcp_err:
            logger.debug("Non-fatal workspace MCP sync warning: %s", mcp_err)

        session_info = {
            "app_id": app.id,
            "app_identifier": f"compassx-app-{app.id}",
            "status": "active",
            "mode": raw_driver_res.get("mode", "docker"),
            "host_type": raw_driver_res.get("host_type") or host_type,
            "host_image": raw_driver_res.get("host_image"),
            "container_id": raw_driver_res.get("container_id"),
            "container_name": raw_driver_res.get("container_name"),
            "dev_port": dev_port,
            "dev_url": dev_url,
            "repo_dir": repo_dir,
            "workspace_id": ws_id,
            "workspace_name": ws_name,
            "workspace_folder": folder_path,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "omnigent_attached": True,
            "omnigent_server_url": omnigent_link.get("server_url"),
            "omnigent_server_connected": omnigent_link.get("server_connected"),
            "omnigent_session_id": omnigent_link.get("session_id"),
            "omnigent_session_url": omnigent_link.get("session_url"),
            "host_id": resolved_host_id,
            "host_name": resolved_host_name,
            "host_online": omnigent_link.get("host_online", True),
            "workspace": omnigent_link.get("workspace", f"/workspaces/{folder_path}"),
        }

        _DEV_SESSIONS[session_key] = session_info
        # Also store by app_id for backward compat
        _DEV_SESSIONS[app.id] = session_info
        return session_info



    def get_dev_session(self, app) -> Dict[str, Any]:
        """Get current status of dev session and Omnigent server."""
        repo_dir = self.get_repo_dir(app)
        dev_driver = driver_factory.get_dev_driver()
        dev_status = dev_driver.get_dev_status(app)
        is_active = dev_status.get("status") == "active"

        dev_url = ingress_service.get_app_dev_url(app, 9201)
        sess_id = f"sess_omnigent_{app.id}"
        session_url = ingress_service.get_omnigent_session_url(sess_id)

        # Fast path if container is not active and not in sessions: return immediately without remote HTTP calls (<0.02s)
        if not is_active and app.id not in _DEV_SESSIONS:
            return {
                "app_id": app.id,
                "status": dev_status.get("status", "stopped"),
                "dev_url": dev_url,
                "repo_dir": repo_dir,
                "omnigent_attached": False,
                "omnigent_server_available": False,
                "omnigent_session_url": session_url,
                "host_id": None,
                "host_name": str(app.name or app.slug or app.id),
                "host_online": False,
                "host_type": dev_status.get("host_type"),
                "host_image": dev_status.get("host_image"),
                "pod_name": dev_status.get("pod_name"),
                "phase": dev_status.get("phase", "Stopped"),
                "mode": dev_status.get("mode", "docker"),
            }

        # Container is active or in memory: resolve Omnigent details (using 10s TTL cache)
        expected_host_id, expected_host_name = self.get_app_host_identity(app)
        server_status = self.check_omnigent_server()
        live_host_id, live_host_name, host_online = self.resolve_live_host(app, expected_host_id)

        if is_active or host_online:
            self.touch_workspace_activity(app.id)

        if app.id in _DEV_SESSIONS:
            sess = _DEV_SESSIONS[app.id]
            sess["status"] = dev_status.get("status", "inactive")
            sess["omnigent_server_available"] = server_status.get("available", False)
            sess["omnigent_server_url"] = server_status.get("server_url") or self.get_omnigent_server_url()
            sess["omnigent_session_url"] = sess.get("omnigent_session_url") or session_url
            sess["host_id"] = live_host_id or sess.get("host_id") or expected_host_id
            sess["host_name"] = live_host_name or sess.get("host_name") or expected_host_name
            sess["host_online"] = host_online or is_active
            sess["phase"] = dev_status.get("phase")
            sess["pod_name"] = dev_status.get("pod_name")
            if dev_status.get("host_type"):
                sess["host_type"] = dev_status.get("host_type")
            if dev_status.get("host_image"):
                sess["host_image"] = dev_status.get("host_image")
            return sess

        return {
            "app_id": app.id,
            "status": dev_status.get("status", "inactive"),
            "dev_url": dev_url,
            "repo_dir": repo_dir,
            "omnigent_attached": is_active,
            "omnigent_server_available": server_status.get("available", False),
            "omnigent_server_url": server_status.get("server_url") or self.get_omnigent_server_url(),
            "omnigent_session_url": session_url,
            "host_id": live_host_id,
            "host_name": live_host_name,
            "host_online": host_online or is_active,
            "host_type": dev_status.get("host_type"),
            "host_image": dev_status.get("host_image"),
            "pod_name": dev_status.get("pod_name"),
            "phase": dev_status.get("phase"),
            "mode": dev_status.get("mode", "docker"),
        }

    def stop_dev_session(self, app) -> Dict[str, Any]:
        """Stop and clean up development sandbox. Workspace folder is kept on PVC."""
        sess = _DEV_SESSIONS.pop(app.id, None)
        mode = sess.get("mode") if sess else None
        ws_id = sess.get("workspace_id") if sess else None

        dev_driver = driver_factory.get_dev_driver(mode)
        dev_driver.stop_dev(app)

        # Mark workspace as stopped in DB
        if ws_id:
            try:
                from app.models.dev_workspace import DevWorkspace
                with _get_system_db() as db:
                    ws = db.query(DevWorkspace).filter(DevWorkspace.id == ws_id).first()
                    if ws:
                        ws.status = "stopped"
                        db.commit()
            except Exception as e:
                logger.warning("Could not update DevWorkspace status: %s", e)

        # Clean composite key too
        if ws_id:
            _DEV_SESSIONS.pop(f"{app.id}:{ws_id}", None)

        return {"status": "stopped", "app_id": app.id}

    def suspend_dev_session(self, app) -> Dict[str, Any]:
        """Suspend development sandbox compute (scale-to-zero) while keeping persistent workspace intact."""
        sess = _DEV_SESSIONS.get(app.id)
        mode = sess.get("mode") if sess else None
        ws_id = sess.get("workspace_id") if sess else None

        dev_driver = driver_factory.get_dev_driver(mode)
        suspended = dev_driver.suspend_dev(app)

        if sess:
            sess["status"] = "suspended"

        if ws_id:
            try:
                from app.models.dev_workspace import DevWorkspace
                with _get_system_db() as db:
                    ws = db.query(DevWorkspace).filter(DevWorkspace.id == ws_id).first()
                    if ws:
                        ws.status = "suspended"
                        db.commit()
            except Exception as e:
                logger.warning("Could not update DevWorkspace status to suspended: %s", e)

        return {"status": "suspended" if suspended else "failed", "app_id": app.id}

    def resume_dev_session(self, app) -> Dict[str, Any]:
        """Resume a suspended dev sandbox compute (scale-to-one)."""
        sess = _DEV_SESSIONS.get(app.id)
        mode = sess.get("mode") if sess else None
        ws_id = sess.get("workspace_id") if sess else None

        dev_driver = driver_factory.get_dev_driver(mode)
        resumed = dev_driver.resume_dev(app)

        if sess:
            sess["status"] = "active"

        if ws_id:
            try:
                from app.models.dev_workspace import DevWorkspace
                with _get_system_db() as db:
                    ws = db.query(DevWorkspace).filter(DevWorkspace.id == ws_id).first()
                    if ws:
                        ws.status = "active"
                        ws.last_active_at = datetime.now(timezone.utc)
                        db.commit()
            except Exception as e:
                logger.warning("Could not update DevWorkspace status to active: %s", e)

        return {"status": "active" if resumed else "failed", "app_id": app.id}

    def touch_workspace_activity(self, app_id: str, workspace_id: Optional[str] = None) -> None:
        """Update last_active_at timestamp for workspace (throttled to at most once per 60s)."""
        import time
        now_ts = time.time()
        key = f"{app_id}:{workspace_id or ''}"
        if (now_ts - _LAST_TOUCHED_WS.get(key, 0)) < 60.0:
            return
        _LAST_TOUCHED_WS[key] = now_ts

        try:
            from app.models.dev_workspace import DevWorkspace
            with _get_system_db() as db:
                query = db.query(DevWorkspace).filter(DevWorkspace.app_id == app_id)
                if workspace_id:
                    query = query.filter((DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id))
                else:
                    query = query.filter(DevWorkspace.status.in_(["active", "suspended"]))
                ws = query.order_by(DevWorkspace.last_active_at.desc().nullslast()).first()
                if ws:
                    ws.last_active_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception:
            pass

    def list_dev_workspaces(self, app) -> List[Dict[str, Any]]:
        """List all dev workspaces for an app with dynamic active status."""
        from app.models.dev_workspace import DevWorkspace
        try:
            # Check currently running session's workspace
            dev_driver = driver_factory.get_dev_driver()
            dev_status = dev_driver.get_dev_status(app)
            is_pod_running = dev_status.get("status") == "active" or dev_status.get("phase") == "Running"

            active_ws_id = None
            if is_pod_running:
                sess = _DEV_SESSIONS.get(app.id) or {}
                active_ws_id = sess.get("workspace_id")

            with _get_system_db() as db:
                workspaces = (
                    db.query(DevWorkspace)
                    .filter(DevWorkspace.app_id == app.id)
                    .order_by(DevWorkspace.last_active_at.desc().nullslast(), DevWorkspace.created_at.desc())
                    .all()
                )
                res = []
                for ws in workspaces:
                    # Dynamically determine if active in running pod
                    is_active = is_pod_running and (
                        ws.id == active_ws_id or
                        (ws.status == "active" and not active_ws_id)
                    )
                    current_branch = ws.git_branch or f"dev/{ws.name}"
                    if is_active and hasattr(dev_driver, "get_live_branch"):
                        try:
                            live_branch = dev_driver.get_live_branch(app, ws.folder_path)
                            if live_branch and live_branch != current_branch:
                                current_branch = live_branch
                                ws.git_branch = live_branch
                                db.commit()
                        except Exception:
                            pass

                    res.append({
                        "id": ws.id,
                        "name": ws.name,
                        "folder_path": ws.folder_path,
                        "git_branch": current_branch,
                        "status": "active" if is_active else "inactive",
                        "size_bytes": ws.size_bytes,
                        "created_by": ws.created_by,
                        "created_at": ws.created_at.isoformat() if ws.created_at else None,
                        "last_active_at": ws.last_active_at.isoformat() if ws.last_active_at else None,
                    })
                return res
        except Exception as e:
            logger.warning("Could not list DevWorkspaces: %s", e)
            return []

    def create_dev_workspace(self, app, name: str, git_branch: Optional[str] = None) -> Dict[str, Any]:
        """Create a new dev workspace record with auto-generated dev/<name> branch and matching folder path."""
        from app.models.dev_workspace import DevWorkspace
        clean_app_id = _clean_id(app.id)
        clean_name = _sanitize_workspace_name(name)
        folder_path = f"{clean_app_id}/{clean_name}"
        branch = git_branch or f"dev/{clean_name}"
        ws_id = clean_name[:32]

        try:
            with _get_system_db() as db:
                existing = db.query(DevWorkspace).filter(
                    DevWorkspace.app_id == app.id,
                    (DevWorkspace.name == clean_name) | (DevWorkspace.id == ws_id),
                ).first()
                if existing:
                    return {
                        "id": existing.id,
                        "name": existing.name,
                        "folder_path": existing.folder_path,
                        "git_branch": existing.git_branch or branch,
                        "status": existing.status,
                        "created_at": existing.created_at.isoformat() if existing.created_at else None,
                        "already_exists": True,
                    }

                id_conflict = db.query(DevWorkspace).filter(DevWorkspace.id == ws_id).first()
                if id_conflict and id_conflict.app_id != app.id:
                    ws_id = f"{clean_name[:24]}_{uuid.uuid4().hex[:6]}"

                ws_record = DevWorkspace(
                    id=ws_id,
                    app_id=app.id,
                    workspace_id=getattr(app, "workspace_id", ""),
                    name=clean_name,
                    folder_path=folder_path,
                    git_branch=branch,
                    status="inactive",
                    created_by=None,
                    last_active_at=datetime.now(timezone.utc),
                )
                db.add(ws_record)
                db.commit()
                db.refresh(ws_record)

                # Proactively create Git worktree inside running container
                try:
                    dev_driver = driver_factory.get_dev_driver()
                    if hasattr(dev_driver, "create_git_worktree"):
                        dev_driver.create_git_worktree(app, folder_path=folder_path, branch=branch)
                except Exception as wt_err:
                    logger.debug("Non-fatal create_git_worktree on workspace creation: %s", wt_err)

                return {
                    "id": ws_record.id,
                    "name": ws_record.name,
                    "folder_path": ws_record.folder_path,
                    "git_branch": ws_record.git_branch,
                    "status": ws_record.status,
                    "created_at": ws_record.created_at.isoformat() if ws_record.created_at else None,
                    "already_exists": False,
                }
        except Exception as e:
            logger.warning("Could not create DevWorkspace: %s", e)
            raise e

    def activate_dev_workspace(self, app, workspace_id: str) -> Dict[str, Any]:
        """Instantly switch the active sandbox without stopping or restarting the container."""
        from app.models.dev_workspace import DevWorkspace
        try:
            with _get_system_db() as db:
                ws = db.query(DevWorkspace).filter(
                    DevWorkspace.app_id == app.id,
                    (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                ).first()
                if not ws:
                    raise ValueError(f"Workspace '{workspace_id}' not found")

                # Set all other workspaces for this app to inactive, target to active
                db.query(DevWorkspace).filter(DevWorkspace.app_id == app.id).update({"status": "inactive"})
                ws.status = "active"
                ws.last_active_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(ws)

                ws_id = ws.id
                folder_path = ws.folder_path
                ws_name = ws.name
                ws_branch = ws.git_branch or f"dev/{ws_name}"

            dev_driver = driver_factory.get_dev_driver()
            # Ensure worktree exists first
            if hasattr(dev_driver, "create_git_worktree"):
                try:
                    dev_driver.create_git_worktree(app, folder_path=folder_path, branch=ws_branch)
                except Exception as e:
                    logger.debug("Non-fatal create_git_worktree on switch: %s", e)

            switch_res = {}
            if hasattr(dev_driver, "switch_active_sandbox"):
                switch_res = dev_driver.switch_active_sandbox(app, folder_path)

            # Update in-memory session mapping
            if app.id in _DEV_SESSIONS:
                _DEV_SESSIONS[app.id]["workspace_id"] = ws_id
                _DEV_SESSIONS[app.id]["workspace_name"] = ws_name
                _DEV_SESSIONS[app.id]["workspace_folder"] = folder_path

            session_key = f"{app.id}:{ws_id}"
            if session_key not in _DEV_SESSIONS and app.id in _DEV_SESSIONS:
                _DEV_SESSIONS[session_key] = dict(_DEV_SESSIONS[app.id])

            return {
                "success": True,
                "workspace_id": ws_id,
                "name": ws_name,
                "folder_path": folder_path,
                "git_branch": ws_branch,
                "status": "active",
                "driver_result": switch_res,
            }
        except Exception as e:
            logger.exception("Failed to activate dev workspace %s for app %s: %s", workspace_id, app.name, e)
            raise e

    def delete_dev_workspace(self, app, workspace_id: str) -> Dict[str, Any]:
        """Delete a dev workspace: remove DB record and worktree folder."""
        from app.models.dev_workspace import DevWorkspace
        try:
            with _get_system_db() as db:
                ws = db.query(DevWorkspace).filter(
                    DevWorkspace.id == workspace_id,
                    DevWorkspace.app_id == app.id,
                ).first()
                if not ws:
                    return {"deleted": False, "reason": "not_found"}
                folder_path = ws.folder_path
                db.delete(ws)
                db.commit()

            # Remove worktree via driver
            try:
                dev_driver = driver_factory.get_dev_driver()
                if hasattr(dev_driver, "remove_git_worktree"):
                    dev_driver.remove_git_worktree(app, folder_path)
                elif hasattr(dev_driver, "delete_workspace_folder"):
                    dev_driver.delete_workspace_folder(folder_path)
            except Exception:
                pass

            # Clean in-memory session
            _DEV_SESSIONS.pop(f"{app.id}:{workspace_id}", None)
            return {"deleted": True, "workspace_id": workspace_id, "folder_path": folder_path}
        except Exception as e:
            logger.warning("Could not delete DevWorkspace %s: %s", workspace_id, e)
            return {"deleted": False, "reason": str(e)}

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

    def _resolve_app_manifest(
        self,
        app,
        dev_driver,
        folder_path: str,
        target_dir: str,
        repo_dir: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve app manifest (app.yaml / app.yml) from host filesystem, falling back to inside dev sandbox."""
        # 1. Try host filesystem first (local-dev driver or shared volume mount)
        manifest_data = app_manifest_service.load_manifest(target_dir) or app_manifest_service.load_manifest(repo_dir)
        if manifest_data:
            return manifest_data

        # 2. If not found on host, probe dev sandbox via dev_driver (Docker container or K8s pod)
        try:
            probe_cmd = (
                "for f in app.yaml app.yml .compass/app.yaml .compass/app.yml; do "
                "  if [ -f \"$f\" ]; then "
                "    echo \"---MANIFEST_FILE:$f---\"; "
                "    cat \"$f\"; "
                "    break; "
                "  fi; "
                "done"
            )
            res = dev_driver.exec_command_in_dev(app, command=probe_cmd, workspace_folder=folder_path)
            output = (res.get("output") or "").strip()
            if "---MANIFEST_FILE:" in output:
                parts = output.split("---MANIFEST_FILE:", 1)[1].split("---", 1)
                manifest_filename = parts[0].strip()
                yaml_content = parts[1].strip() if len(parts) > 1 else ""
                parsed = app_manifest_service.parse_manifest_text(yaml_content, manifest_filename)
                if parsed:
                    logger.info("Resolved app manifest '%s' directly from dev sandbox (%s)", manifest_filename, getattr(dev_driver, '__class__', {}).__name__)
                    return parsed
        except Exception as e:
            logger.debug("Sandbox manifest probe failed: %s", e)

        return None

    def install_dev_dependencies(
        self,
        app,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Verify and install dependencies (pip / npm) inside active dev sandbox."""
        sess = _DEV_SESSIONS.get(app.id)
        mode = sess.get("mode") if sess else None
        dev_driver = driver_factory.get_dev_driver(mode)
        clean_id = _clean_id(app.id)
        ws_name = "default"
        if workspace_name:
            ws_name = _sanitize_workspace_name(workspace_name)
        elif workspace_id:
            try:
                from app.models.dev_workspace import DevWorkspace
                with _get_system_db() as db:
                    ws = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                    ).first()
                    if ws and ws.name:
                        ws_name = ws.name
            except Exception:
                ws_name = workspace_id
        folder_path = f"{clean_id}/{ws_name}"
        repo_dir = self.get_repo_dir(app)
        target_dir = repo_dir
        if workspace_name:
            ws_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
            if os.path.exists(ws_dir):
                target_dir = ws_dir

        manifest_data = self._resolve_app_manifest(app, dev_driver, folder_path, target_dir, repo_dir)
        custom_install_cmd = app_manifest_service.get_install_command(manifest_data)
        env_exports = app_manifest_service.get_env_exports(manifest_data)

        # 1. If app.yaml declares custom install command, prioritize it!
        if custom_install_cmd:
            raw_path = (manifest_data or {}).get("_manifest_path", "app.yaml")
            if os.path.isabs(raw_path) and os.path.exists(target_dir):
                try:
                    manifest_file = os.path.relpath(raw_path, target_dir).replace("\\", "/")
                except Exception:
                    manifest_file = os.path.basename(raw_path)
            else:
                manifest_file = raw_path.replace("\\", "/")

            hash_check_cmd = f"cat '{manifest_file}' 2>/dev/null | md5sum | awk '{{print $1}}'"
            hash_res = dev_driver.exec_command_in_dev(app, command=hash_check_cmd, workspace_folder=folder_path)
            current_hash = (hash_res.get("output") or "").strip().split()[0] if hash_res.get("output") else ""

            hash_file = f"/tmp/.deps_{clean_id}_hash"
            if not force and current_hash:
                cache_check_cmd = f"test -f '{hash_file}' && grep -q '{current_hash}' '{hash_file}' && echo 'CACHED'"
                cache_res = dev_driver.exec_command_in_dev(app, command=cache_check_cmd, workspace_folder=folder_path)
                if "CACHED" in (cache_res.get("output") or ""):
                    return {
                        "success": True,
                        "cached": True,
                        "manifests": [manifest_file],
                        "message": "Dependencies already up-to-date (app.yaml).",
                        "output": f"Dependencies already verified and up-to-date from app.yaml (hash: {current_hash[:8]}).",
                    }

            full_install_cmd = f"{env_exports} {custom_install_cmd}" if env_exports else custom_install_cmd
            exec_res = dev_driver.exec_command_in_dev(app, command=full_install_cmd, workspace_folder=folder_path)
            success = exec_res.get("success", False)
            output = exec_res.get("output", "")

            if success and current_hash:
                dev_driver.exec_command_in_dev(app, command=f"echo '{current_hash}' > '{hash_file}'", workspace_folder=folder_path)

            return {
                "success": success,
                "cached": False,
                "manifests": [manifest_file],
                "exit_code": exec_res.get("exit_code", 0),
                "output": f"[app.yaml] Executed install command: {custom_install_cmd}\n{output}".strip(),
                "message": "Libraries installed successfully from app.yaml." if success else "Failed to install libraries defined in app.yaml.",
            }

        # 2. Probe for dependency manifests (requirements.txt, package.json across root & subdirectories)
        probe_cmd = (
            "find . -maxdepth 3 -not -path '*/.*' -not -path '*/node_modules/*' -not -path '*/.venv/*' "
            "\\( -name requirements.txt -o -name package.json \\) 2>/dev/null | sed 's|^\\./||'"
        )
        probe_res = dev_driver.exec_command_in_dev(app, command=probe_cmd, workspace_folder=folder_path)
        manifests = [line.strip() for line in (probe_res.get("output") or "").splitlines() if line.strip() and not line.startswith("bash:")]
        if manifest_data and os.path.exists(manifest_data.get("_manifest_path", "")):
            manifest_rel = os.path.relpath(manifest_data["_manifest_path"], target_dir).replace("\\", "/")
            if manifest_rel not in manifests:
                manifests.append(manifest_rel)

        if not manifests:
            return {
                "success": True,
                "cached": True,
                "manifests": [],
                "message": "No requirements.txt, package.json, or app.yaml found. Ready.",
                "output": "No application dependency manifests detected in workspace.",
            }

        # 3. Check hash cache if not forced
        hash_check_cmd = (
            "cat " + " ".join(manifests) + " 2>/dev/null | md5sum | awk '{print $1}'"
        )
        hash_res = dev_driver.exec_command_in_dev(app, command=hash_check_cmd, workspace_folder=folder_path)
        current_hash = (hash_res.get("output") or "").strip().split()[0] if hash_res.get("output") else ""

        hash_file = f"/tmp/.deps_{clean_id}_hash"
        if not force and current_hash:
            cache_check_cmd = f"test -f '{hash_file}' && grep -q '{current_hash}' '{hash_file}' && echo 'CACHED'"
            cache_res = dev_driver.exec_command_in_dev(app, command=cache_check_cmd, workspace_folder=folder_path)
            if "CACHED" in (cache_res.get("output") or ""):
                return {
                    "success": True,
                    "cached": True,
                    "manifests": manifests,
                    "message": "Dependencies already up-to-date.",
                    "output": f"Dependencies already verified and up-to-date (hash: {current_hash[:8]}).",
                }

        # 4. Execute installation inside dev container
        install_commands = []
        for m in manifests:
            if m.endswith("requirements.txt"):
                d = os.path.dirname(m)
                prefix = f"cd '{d}' && " if d else ""
                suffix = " && cd -" if d else ""
                install_commands.append(f"{prefix}pip3 install --prefer-binary -r requirements.txt{suffix}")
            elif m.endswith("package.json"):
                d = os.path.dirname(m)
                prefix = f"cd '{d}' && " if d else ""
                suffix = " && cd -" if d else ""
                install_commands.append(f"{prefix}npm install --prefer-offline --no-audit{suffix}")

        full_install_cmd = " && ".join(install_commands)
        exec_res = dev_driver.exec_command_in_dev(app, command=full_install_cmd, workspace_folder=folder_path)

        success = exec_res.get("success", False)
        output = exec_res.get("output", "")

        if success and current_hash:
            dev_driver.exec_command_in_dev(app, command=f"echo '{current_hash}' > '{hash_file}'", workspace_folder=folder_path)

        return {
            "success": success,
            "cached": False,
            "manifests": manifests,
            "exit_code": exec_res.get("exit_code", 0),
            "output": output,
            "message": "Libraries installed successfully." if success else "Failed to install libraries.",
        }

    def verify_git_workspace(
        self,
        app,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify git status, active branch, and codebase state inside active dev sandbox."""
        sess = _DEV_SESSIONS.get(app.id)
        mode = sess.get("mode") if sess else None
        dev_driver = driver_factory.get_dev_driver(mode)
        clean_id = _clean_id(app.id)
        ws_name = "default"
        target_branch = None
        if workspace_name:
            ws_name = _sanitize_workspace_name(workspace_name)
        elif workspace_id:
            try:
                from app.models.dev_workspace import DevWorkspace
                with _get_system_db() as db:
                    ws = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                    ).first()
                    if ws:
                        if ws.name:
                            ws_name = ws.name
                        if ws.git_branch:
                            target_branch = ws.git_branch
            except Exception:
                ws_name = workspace_id
        folder_path = f"{clean_id}/{ws_name}"
        if not target_branch:
            target_branch = f"dev/{ws_name}" if ws_name != "default" else getattr(app, "git_branch", "main")

        git_check_cmd = (
            "echo '=== Git Workspace Verification ==='; "
            "if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then "
            "  echo '[WARN] Working directory is not a git repository.'; "
            "  echo '[INFO] Working directory: ' $(pwd); "
            "  echo '[SUCCESS] Workspace codebase verified and ready.'; "
            "  exit 0; "
            "fi; "
            "cur_branch=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'HEAD'); "
            "echo \"[INFO] Current active branch: $cur_branch\"; "
            "target_branch='" + target_branch + "'; "
            "if [ -n \"$target_branch\" ] && [ \"$cur_branch\" != \"$target_branch\" ]; then "
            "  echo \"[GIT] Attempting switch to workspace branch: $target_branch...\"; "
            "  if git checkout \"$target_branch\" 2>/dev/null || git checkout -b \"$target_branch\" 2>/dev/null; then "
            "    cur_branch=$(git branch --show-current 2>/dev/null || echo \"$target_branch\"); "
            "    echo \"[INFO] Switched active branch to: $cur_branch\"; "
            "  else "
            "    echo \"[NOTICE] Retained active branch '$cur_branch' to preserve local working tree files.\"; "
            "  fi; "
            "fi; "
            "head_commit=$(git log -1 --format='%h - %s (%cr)' 2>/dev/null || echo 'initial'); "
            "echo \"[INFO] Head commit: $head_commit\"; "
            "remote_url=$(git config --get remote.origin.url 2>/dev/null || echo 'local'); "
            "safe_remote=$(echo \"$remote_url\" | sed -E 's/:\/\/[^@]*@/:\/\/****@/'); "
            "echo \"[INFO] Remote origin: $safe_remote\"; "
            "changed_count=$(git status --porcelain -uno 2>/dev/null | wc -l | tr -d ' '); "
            "echo \"[INFO] Working tree status: $changed_count uncommitted / modified file(s)\"; "
            "echo '[SUCCESS] Workspace codebase verified and ready for development.'"
        )

        exec_res = dev_driver.exec_command_in_dev(app, command=git_check_cmd, workspace_folder=folder_path)
        output = (exec_res.get("output") or "").strip()
        success = exec_res.get("success", False)

        return {
            "success": success or ("Workspace codebase verified" in output),
            "branch": target_branch,
            "output": output,
            "message": "Workspace codebase verified and ready.",
        }

    def run_dev_app(
        self,
        app,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Detect and start dev application processes (FastAPI backend and/or Vite frontend) inside container."""
        sess = _DEV_SESSIONS.get(app.id)
        mode = sess.get("mode") if sess else None
        dev_driver = driver_factory.get_dev_driver(mode)
        clean_id = _clean_id(app.id)
        ws_name = "default"
        if workspace_name:
            ws_name = _sanitize_workspace_name(workspace_name)
        elif workspace_id:
            try:
                from app.models.dev_workspace import DevWorkspace
                with _get_system_db() as db:
                    ws = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                    ).first()
                    if ws and ws.name:
                        ws_name = ws.name
            except Exception:
                ws_name = workspace_id
        folder_path = f"{clean_id}/{ws_name}"
        dev_url = sess.get("dev_url") if sess else ""
        repo_dir = self.get_repo_dir(app)
        target_dir = repo_dir
        if workspace_name:
            ws_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
            if os.path.exists(ws_dir):
                target_dir = ws_dir

        manifest_data = self._resolve_app_manifest(app, dev_driver, folder_path, target_dir, repo_dir)
        run_cfg = app_manifest_service.get_run_config(manifest_data)

        if run_cfg:
            backend_cmd = run_cfg.get("backend_command")
            backend_dir = run_cfg.get("backend_dir")
            frontend_cmd = run_cfg.get("frontend_command")
            frontend_dir = run_cfg.get("frontend_dir")
            env_exports = run_cfg.get("env_exports", "")

            run_script_parts = [
                "echo '=== Application Runtime Initialization (app.yaml) ===';",
            ]
            if env_exports:
                run_script_parts.append(env_exports)

            if backend_cmd and frontend_cmd:
                b_prefix = f"cd '{backend_dir}' && " if backend_dir else ""
                f_prefix = f"cd '{frontend_dir}' && " if frontend_dir else ""
                run_script_parts.append(
                    f"if (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8000[[:space:]]'; then "
                    f"  echo '[backend] Backend service active on port 8000 (app.yaml)'; "
                    f"else "
                    f"  echo '[backend] Starting backend from app.yaml: {backend_cmd}...'; "
                    f"  ({b_prefix}nohup {backend_cmd} > /tmp/app_backend.log 2>&1 &); "
                    f"fi; "
                    f"if (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8080[[:space:]]'; then "
                    f"  echo '[frontend] Frontend service active on port 8080 (app.yaml)'; "
                    f"else "
                    f"  echo '[frontend] Starting frontend from app.yaml: {frontend_cmd}...'; "
                    f"  ({f_prefix}nohup {frontend_cmd} > /tmp/app_frontend.log 2>&1 &); "
                    f"fi;"
                )
            elif backend_cmd:
                b_prefix = f"cd '{backend_dir}' && " if backend_dir else ""
                run_script_parts.append(
                    f"if (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8080[[:space:]]' || (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8000[[:space:]]'; then "
                    f"  echo '[app] Application service active (app.yaml)'; "
                    f"else "
                    f"  echo '[app] Starting service from app.yaml: {backend_cmd}...'; "
                    f"  ({b_prefix}nohup {backend_cmd} > /tmp/app_service.log 2>&1 &); "
                    f"fi;"
                )
            elif frontend_cmd:
                f_prefix = f"cd '{frontend_dir}' && " if frontend_dir else ""
                run_script_parts.append(
                    f"if (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8080[[:space:]]'; then "
                    f"  echo '[frontend] Frontend service active on port 8080 (app.yaml)'; "
                    f"else "
                    f"  echo '[frontend] Starting frontend from app.yaml: {frontend_cmd}...'; "
                    f"  ({f_prefix}nohup {frontend_cmd} > /tmp/app_frontend.log 2>&1 &); "
                    f"fi;"
                )

            run_script_parts.append(
                "sleep 2; "
                "echo '=== Health Verification ==='; "
                "if (curl -fsSL --connect-timeout 2 http://localhost:8080 >/dev/null 2>&1 || wget -q -O - http://localhost:8080 >/dev/null 2>&1); then "
                "  echo '[health] Application responding on port 8080'; "
                "elif (curl -fsSL --connect-timeout 2 http://localhost:8000 >/dev/null 2>&1 || wget -q -O - http://localhost:8000 >/dev/null 2>&1); then "
                "  echo '[health] Application responding on port 8000'; "
                "else "
                "  echo '[health] Application processes launched and listening.'; "
                "fi; "
                "echo '[SUCCESS] Application dev runtime is running and ready.'"
            )
            run_script = " ".join(run_script_parts)
        else:
            run_script = (
                "echo '=== Application Runtime Initialization ==='; "
                "BACKEND_FILE=$(find . -maxdepth 3 -not -path '*/.*' -not -path '*/node_modules/*' -not -path '*/.venv/*' \\( -name 'main.py' -o -name 'app.py' \\) 2>/dev/null | head -n 1 | sed 's|^\\./||'); "
                "FRONTEND_FILE=$(find . -maxdepth 3 -not -path '*/.*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -name 'package.json' 2>/dev/null | head -n 1 | sed 's|^\\./||'); "
                # 1. Start Python backend if detected
                "if [ -n \"$BACKEND_FILE\" ]; then "
                "  B_DIR=$(dirname \"$BACKEND_FILE\"); "
                "  B_BASE=$(basename \"$BACKEND_FILE\" .py); "
                "  if (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8000[[:space:]]'; then "
                "    echo \"[backend] Uvicorn service active on port 8000 ($BACKEND_FILE)\"; "
                "  else "
                "    echo \"[backend] Starting Uvicorn backend on port 8000 ($BACKEND_FILE)...\"; "
                "    (cd \"$B_DIR\" && nohup uvicorn \"$B_BASE:app\" --host 0.0.0.0 --port 8000 --reload --reload-delay 2.0 > /tmp/app_backend.log 2>&1 &); "
                "  fi; "
                "fi; "
                # 2. Start Frontend / Vite dev server if detected
                "if [ -n \"$FRONTEND_FILE\" ]; then "
                "  F_DIR=$(dirname \"$FRONTEND_FILE\"); "
                "  if (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8080[[:space:]]'; then "
                "    echo \"[frontend] Frontend service active on port 8080 ($FRONTEND_FILE)\"; "
                "  else "
                "    echo \"[frontend] Starting Vite dev server on port 8080 ($FRONTEND_FILE)...\"; "
                "    (cd \"$F_DIR\" && nohup npx vite --host 0.0.0.0 --port 8080 --cors > /tmp/app_frontend.log 2>&1 &); "
                "  fi; "
                "elif [ -n \"$BACKEND_FILE\" ] && [ -z \"$FRONTEND_FILE\" ]; then "
                "  B_DIR=$(dirname \"$BACKEND_FILE\"); "
                "  B_BASE=$(basename \"$BACKEND_FILE\" .py); "
                "  if ! (ss -tln 2>/dev/null || netstat -an 2>/dev/null) | grep -qE '[:.]8080[[:space:]]'; then "
                "    (cd \"$B_DIR\" && nohup uvicorn \"$B_BASE:app\" --host 0.0.0.0 --port 8080 --reload --reload-delay 2.0 > /tmp/app_backend_8080.log 2>&1 &); "
                "  fi; "
                "fi; "
                # 3. Health check probe
                "sleep 2; "
                "echo '=== Health Verification ==='; "
                "if (curl -fsSL --connect-timeout 2 http://localhost:8080 >/dev/null 2>&1 || wget -q -O - http://localhost:8080 >/dev/null 2>&1); then "
                "  echo '[health] Web frontend responding on port 8080'; "
                "elif (curl -fsSL --connect-timeout 2 http://localhost:8000 >/dev/null 2>&1 || wget -q -O - http://localhost:8000 >/dev/null 2>&1); then "
                "  echo '[health] Backend API responding on port 8000'; "
                "else "
                "  echo '[health] Application processes launched and listening.'; "
                "fi; "
                "echo '[SUCCESS] Application dev runtime is running and ready.'"
            )

        exec_res = dev_driver.exec_command_in_dev(app, command=run_script, workspace_folder=folder_path)
        output = (exec_res.get("output") or "").strip()
        success = exec_res.get("success", False) or ("Application dev runtime is running and ready" in output)

        return {
            "success": success,
            "dev_url": dev_url,
            "output": output,
            "message": "Application running successfully." if success else "Failed to start application services.",
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
                    stat = os.stat(full_path)
                    size = stat.st_size
                    mtime = int(stat.st_mtime * 1000)
                except Exception:
                    size = 0
                    mtime = 0
                file_tree.append({
                    "path": rel_path,
                    "name": file,
                    "size": size,
                    "bytes": size,
                    "ext": os.path.splitext(file)[1].lstrip("."),
                    "modified_at": mtime,
                })

        return sorted(file_tree, key=lambda x: x["path"])

    def read_workspace_file(self, app, file_path: str) -> Dict[str, Any]:
        """Read text content of a workspace file."""
        self.touch_workspace_activity(app.id)
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
        self.touch_workspace_activity(app.id)
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

    # ── Git Publish (Per-Workspace Push to Remote) ─────────────────────────

    def publish_dev_changes(
        self,
        app,
        commit_message: Optional[str] = None,
        user_id: str = "system",
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Commit all modified files in the targeted workspace to its dedicated Git branch and push to remote.
        Decoupled: Does NOT stop dev sandbox. Does NOT trigger production deployment.
        """
        from app.models.dev_workspace import DevWorkspace

        target_ws = None
        clean_app_id = _clean_id(app.id)

        # 1. Resolve workspace from parameter, active in-memory session, or latest DB record
        try:
            with _get_system_db() as db:
                if workspace_id:
                    target_ws = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.id == workspace_id) | (DevWorkspace.name == workspace_id),
                    ).first()
                elif workspace_name:
                    clean_name = _sanitize_workspace_name(workspace_name)
                    target_ws = db.query(DevWorkspace).filter(
                        DevWorkspace.app_id == app.id,
                        (DevWorkspace.name == clean_name) | (DevWorkspace.id == clean_name[:32]),
                    ).first()

                if not target_ws and app.id in _DEV_SESSIONS:
                    sess_ws_id = _DEV_SESSIONS[app.id].get("workspace_id")
                    if sess_ws_id:
                        target_ws = db.query(DevWorkspace).filter(
                            DevWorkspace.app_id == app.id,
                            DevWorkspace.id == sess_ws_id,
                        ).first()

                if not target_ws:
                    target_ws = (
                        db.query(DevWorkspace)
                        .filter(DevWorkspace.app_id == app.id)
                        .order_by(DevWorkspace.last_active_at.desc().nullslast(), DevWorkspace.created_at.desc())
                        .first()
                    )
        except Exception as ws_err:
            logger.warning("Could not query target DevWorkspace: %s", ws_err)

        folder_name = target_ws.name if target_ws else (_DEV_SESSIONS.get(app.id, {}).get("workspace_name") or "default")
        folder_path = target_ws.folder_path if target_ws else f"{clean_app_id}/{folder_name}"

        # Check live branch inside the container
        dev_driver = driver_factory.get_dev_driver()
        live_branch = None
        if hasattr(dev_driver, "get_live_branch"):
            try:
                live_branch = dev_driver.get_live_branch(app, folder_path)
            except Exception:
                pass

        # Resolve branch
        if live_branch:
            branch = live_branch
            if target_ws:
                try:
                    with _get_system_db() as db:
                        db_ws = db.query(DevWorkspace).filter(DevWorkspace.id == target_ws.id).first()
                        if db_ws and db_ws.git_branch != live_branch:
                            db_ws.git_branch = live_branch
                            db.commit()
                except Exception:
                    pass
        elif target_ws and target_ws.git_branch and target_ws.git_branch != "main":
            branch = target_ws.git_branch
        elif folder_name and folder_name != "default":
            branch = f"dev/{folder_name}"
            if target_ws:
                try:
                    with _get_system_db() as db:
                        db_ws = db.query(DevWorkspace).filter(DevWorkspace.id == target_ws.id).first()
                        if db_ws:
                            db_ws.git_branch = branch
                            db.commit()
                except Exception:
                    pass
        else:
            branch = (target_ws.git_branch if target_ws else None) or getattr(app, "git_branch", None) or "main"

        # 2. Authenticated Git Push URL
        git_url = getattr(app, "git_repo_url", None) or ""
        git_token = None
        if hasattr(app, "git_pat_enc") and app.git_pat_enc:
            try:
                from app.services.encryption import decrypt_field
                git_token = decrypt_field(app.git_pat_enc)
            except Exception as enc_err:
                logger.warning("Could not decrypt PAT token: %s", enc_err)

        auth_url = git_url
        if git_token and git_url and "github.com" in git_url and not ("@" in git_url.split("//")[-1]):
            auth_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")
        elif git_token and git_url and not ("@" in git_url.split("//")[-1]):
            auth_url = git_url.replace("https://", f"https://oauth2:{git_token}@")

        msg = (commit_message or "").strip() or f"Dev updates [{folder_name}] - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

        # 3. Ensure Dev Pod is running if currently stopped
        dev_driver = driver_factory.get_dev_driver()
        dev_status = dev_driver.get_dev_status(app)
        is_running = dev_status.get("status") == "active" or dev_status.get("phase") == "Running"
        if not is_running:
            try:
                repo_dir = self.get_repo_dir(app)
                self.start_dev_session(
                    app,
                    repo_dir,
                    workspace_id=target_ws.id if target_ws else None,
                    workspace_name=folder_name,
                )
                import time
                for _ in range(8):
                    time.sleep(1.0)
                    st = dev_driver.get_dev_status(app)
                    if st.get("status") == "active" or st.get("phase") == "Running":
                        break
            except Exception as start_err:
                logger.warning("Could not auto-start dev pod for push: %s", start_err)

        # 4. Execute Git commit & push inside the target workspace folder via driver
        git_res = dev_driver.exec_git_in_workspace(
            app=app,
            workspace_folder=folder_path,
            commit_message=msg,
            branch=branch,
            auth_url=auth_url,
        )

        commit_sha = git_res.get("commit_sha") or ""
        git_output = git_res.get("output") or ""
        success = git_res.get("success", False)

        # Fallback to local server repo if driver exec failed or was unavailable
        if not success:
            repo_dir = self.get_repo_dir(app)
            if os.path.exists(repo_dir):
                try:
                    git_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
                    if auth_url:
                        subprocess.run(["git", "-c", "credential.helper=", "remote", "set-url", "origin", auth_url], cwd=repo_dir, env=git_env, capture_output=True, text=True, check=False)
                    subprocess.run(["git", "-c", "core.longpaths=true", "checkout", "-B", branch], cwd=repo_dir, env=git_env, capture_output=True, text=True, check=False)
                    subprocess.run(["git", "-c", "core.longpaths=true", "add", "."], cwd=repo_dir, env=git_env, capture_output=True, text=True, check=False)
                    subprocess.run(["git", "-c", "core.longpaths=true", "commit", "-m", msg], cwd=repo_dir, env=git_env, capture_output=True, text=True, check=False)
                    p_res = subprocess.run(["git", "-c", "credential.helper=", "-c", "core.longpaths=true", "push", "-u", "origin", branch], cwd=repo_dir, env=git_env, capture_output=True, text=True, check=False)
                    fallback_out = (p_res.stdout or "") + (p_res.stderr or "")
                    if p_res.returncode == 0:
                        success = True
                        git_output = fallback_out
                        s_res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, env=git_env, capture_output=True, text=True, check=False)
                        commit_sha = (s_res.stdout or "").strip()
                    else:
                        git_output = (git_output + "\n" + fallback_out).strip()
                except Exception as fallback_err:
                    logger.warning("Local repo Git publish fallback error: %s", fallback_err)

        if not success:
            error_details = git_res.get("error") or git_output or "Git push failed without error output"
            if "Authentication failed" in error_details or "could not read Username" in error_details or "Permission to" in error_details:
                error_msg = f"Git Push Failed (Authentication Error): The repository denied write access. Please verify that a Personal Access Token (PAT) with write permissions is configured on this app. Output: {error_details}"
            else:
                error_msg = f"Git Push Failed: {error_details}"
            logger.error("Publish changes failed for app %s: %s", app.id, error_msg)
            raise RuntimeError(error_msg)

        return {
            "status": "pushed",
            "workspace_id": target_ws.id if target_ws else None,
            "workspace_name": folder_name,
            "workspace_folder": folder_path,
            "git_branch": branch,
            "commit_message": msg,
            "commit_sha": commit_sha,
            "git_output": git_output,
            "pushed_to_remote": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_omnigent_agents(self) -> List[Dict[str, Any]]:
        """Fetch list of available agents from Omnigent central server."""
        import urllib.request
        import json

        urls = []
        int_url = self.get_omnigent_internal_url()
        pub_url = self.get_omnigent_server_url()
        if int_url:
            urls.append(int_url)
        if pub_url and pub_url not in urls:
            urls.append(pub_url)

        for u in urls:
            try:
                req = urllib.request.Request(f"{u}/v1/agents", headers={"User-Agent": "CompassX/1.0"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    data = json.loads(resp.read().decode())
                    agents = data.get("agents") or data.get("data") or (data if isinstance(data, list) else [])
                    if agents:
                        return agents
            except Exception as e:
                logger.debug("Could not fetch agents from %s: %s", u, e)

        # Default & comprehensive agent roster matching Omnigent & AI ecosystems
        return [
            {
                "id": "agent_claude_code",
                "name": "claude-code",
                "display_name": "Claude Code",
                "provider": "Anthropic",
                "description": "Agentic coding CLI assistant with autonomous file editing, git operations, and terminal execution",
                "role": "Autonomous Coding Agent",
                "icon": "terminal",
                "badge": "Claude 3.7",
                "color": "#d97706",
            },
            {
                "id": "agent_antigravity",
                "name": "antigravity-native-ui",
                "display_name": "Antigravity",
                "provider": "Google DeepMind",
                "description": "Google DeepMind Antigravity Pair Programmer for fast code refactoring, system architecture, and verification",
                "role": "Lead Architect & Pair Programmer",
                "icon": "sparkles",
                "badge": "Advanced AGY",
                "color": "#6366f1",
            },
            {
                "id": "agent_polly",
                "name": "polly",
                "display_name": "Omnigent Polly",
                "provider": "Omnigent",
                "description": "Full-stack AI developer for interactive development, debugging, and UI styling",
                "role": "Full-Stack AI Developer",
                "icon": "bot",
                "badge": "Generalist",
                "color": "#8b5cf6",
            },
            {
                "id": "agent_opencode",
                "name": "opencode-native-ui",
                "display_name": "OpenCode",
                "provider": "OpenCode",
                "description": "OpenCode terminal and file system execution agent specialized in background commands",
                "role": "Terminal & Shell Specialist",
                "icon": "code",
                "badge": "Shell First",
                "color": "#10b981",
            },
            {
                "id": "agent_codex",
                "name": "codex-native-ui",
                "display_name": "Codex UI",
                "provider": "OpenAI",
                "description": "Codex UI assistant specialized in frontend design, CSS layouts, and React components",
                "role": "Frontend Specialist",
                "icon": "layout",
                "badge": "UI & Components",
                "color": "#0284c7",
            },
            {
                "id": "agent_gemini_cli",
                "name": "gemini-cli",
                "display_name": "Gemini CLI",
                "provider": "Google",
                "description": "Google Gemini 2.0 Pro ultra-fast code intelligence and multi-turn refactoring",
                "role": "Fast Reasoning Agent",
                "icon": "zap",
                "badge": "Gemini 2.0",
                "color": "#ec4899",
            },
            {
                "id": "agent_deepseek_coder",
                "name": "deepseek-coder",
                "display_name": "DeepSeek Coder",
                "provider": "DeepSeek",
                "description": "DeepSeek R1 / V3 deep mathematical reasoning, complex algorithms, and backend logic",
                "role": "Logic & Algorithm Specialist",
                "icon": "cpu",
                "badge": "Deep Reasoning",
                "color": "#06b6d4",
            },
        ]

    def create_omnigent_chat_session(
        self,
        app,
        agent_name: Optional[str] = "polly",
        title: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or initialize an interactive Omnigent chat session bound to the active app workspace."""
        import urllib.request
        import json

        server_status = self.ensure_omnigent_server()
        url = server_status.get("internal_url") or server_status.get("server_url") or self.get_omnigent_internal_url()
        expected_host_id, expected_host_name = self.get_app_host_identity(app)
        live_host_id, live_host_name, host_online = self.resolve_live_host(app, expected_host_id)

        # Get active workspace folder
        from app.models.dev_workspace import DevWorkspace
        ws_folder = None
        ws_name = None
        target_ws_id = workspace_id
        try:
            with _get_system_db() as db:
                if target_ws_id:
                    ws = db.query(DevWorkspace).filter(DevWorkspace.app_id == app.id, DevWorkspace.id == target_ws_id).first()
                else:
                    ws = db.query(DevWorkspace).filter(DevWorkspace.app_id == app.id, DevWorkspace.status == "active").first()
                if ws:
                    ws_folder = ws.folder_path
                    ws_name = ws.name
                    target_ws_id = ws.id
        except Exception as e:
            logger.debug("Could not resolve dev workspace from DB: %s", e)

        if not ws_folder:
            ws_folder = _clean_id(app.id)

        ws_path = f"/workspaces/{ws_folder}"

        # Resolve agent_id
        agents = self.get_omnigent_agents()
        agent_id = None
        for ag in agents:
            if ag.get("name") == agent_name or ag.get("id") == agent_name:
                agent_id = ag.get("id")
                break
        if not agent_id and agents:
            agent_id = agents[0].get("id")
        if not agent_id:
            agent_id = "agent_polly"

        payload_dict = {
            "title": title or f"Build Studio: {app.name}",
            "agent_id": agent_id,
            "host_id": live_host_id,
            "workspace": ws_path,
        }

        session_id = None
        res_data = {}
        try:
            req = urllib.request.Request(
                f"{url}/v1/sessions",
                data=json.dumps(payload_dict).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "CompassX/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                res_data = json.loads(resp.read().decode())
                session_id = res_data.get("id") or res_data.get("session_id")
        except Exception as e:
            logger.warning("Could not create remote Omnigent session on %s: %s", url, e)

        if not session_id:
            session_id = f"sess_build_{app.id}_{uuid.uuid4().hex[:8]}"

        session_info = {
            "session_id": session_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "title": title or f"Build Studio: {app.name}",
            "host_id": live_host_id,
            "host_name": live_host_name,
            "host_online": host_online,
            "workspace_id": target_ws_id,
            "workspace_name": ws_name,
            "workspace_folder": ws_folder,
            "workspace_path": ws_path,
            "server_url": url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache in memory
        if app.id not in _DEV_SESSIONS:
            _DEV_SESSIONS[app.id] = {}
        _DEV_SESSIONS[app.id]["build_session"] = session_info
        _DEV_SESSIONS[app.id]["build_session_id"] = session_id

        return session_info

    def get_build_session(self, app, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Get or lazily initialize the active Build Studio session for this app."""
        dev_status = self.get_dev_session(app)
        is_pod_running = dev_status.get("status") == "active" or dev_status.get("host_online", False)

        # Check existing cached session
        existing = (_DEV_SESSIONS.get(app.id) or {}).get("build_session")
        if existing and existing.get("session_id"):
            existing["dev_status"] = dev_status.get("status", "inactive")
            existing["dev_url"] = dev_status.get("dev_url") or ingress_service.get_app_dev_url(app, 9201)
            existing["is_running"] = is_pod_running
            existing["host_online"] = dev_status.get("host_online", False)
            return existing

        # Create new session
        session_info = self.create_omnigent_chat_session(app, workspace_id=workspace_id)
        session_info["dev_status"] = dev_status.get("status", "inactive")
        session_info["dev_url"] = dev_status.get("dev_url") or ingress_service.get_app_dev_url(app, 9201)
        session_info["is_running"] = is_pod_running
        return session_info

    def get_build_session_messages(self, app, session_id: str) -> List[Dict[str, Any]]:
        """Fetch items/messages from Omnigent Server for the specified session."""
        import urllib.request
        import json

        urls = []
        int_url = self.get_omnigent_internal_url()
        pub_url = self.get_omnigent_server_url()
        if int_url:
            urls.append(int_url)
        if pub_url and pub_url not in urls:
            urls.append(pub_url)

        for u in urls:
            try:
                req = urllib.request.Request(f"{u}/v1/sessions/{session_id}/items", headers={"User-Agent": "CompassX/1.0"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    data = json.loads(resp.read().decode())
                    raw_items = data.get("items") or (data if isinstance(data, list) else [])

                    # Normalize raw Omnigent items to UI chat format
                    messages = []
                    for it in raw_items:
                        it_type = it.get("type", "message")
                        content = it.get("content") or it.get("text") or ""
                        role = it.get("role") or ("user" if it_type == "comment" else "assistant")

                        msg = {
                            "id": str(it.get("id") or uuid.uuid4().hex[:8]),
                            "role": role,
                            "type": it_type,
                            "content": content,
                            "agent": it.get("agent") or it.get("agent_name"),
                            "status": it.get("status", "completed"),
                            "created_at": it.get("created_at") or datetime.now(timezone.utc).isoformat(),
                            "tool": it.get("tool") or (
                                {
                                    "name": it.get("tool_name") or it.get("name"),
                                    "input": it.get("input") or it.get("arguments"),
                                    "output": it.get("output") or it.get("result"),
                                    "status": it.get("status", "completed"),
                                }
                                if it_type in ["tool_use", "tool_call", "tool_result", "command", "file_edit"]
                                else None
                            ),
                        }
                        messages.append(msg)
                    return messages
            except Exception as e:
                logger.debug("Could not fetch session items from %s: %s", u, e)

        return []

    def send_build_session_prompt(
        self,
        app,
        session_id: str,
        prompt: str,
        agent_name: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Post a user instruction / comment to the Omnigent Server session to trigger the AI agent."""
        import urllib.request
        import json

        self.touch_workspace_activity(app.id, workspace_id)

        urls = []
        int_url = self.get_omnigent_internal_url()
        pub_url = self.get_omnigent_server_url()
        if int_url:
            urls.append(int_url)
        if pub_url and pub_url not in urls:
            urls.append(pub_url)

        payload = json.dumps({"content": prompt, "agent": agent_name}).encode("utf-8")

        for u in urls:
            try:
                req = urllib.request.Request(
                    f"{u}/v1/sessions/{session_id}/comments",
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "CompassX/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    res_data = json.loads(resp.read().decode())
                    return {
                        "status": "sent",
                        "session_id": session_id,
                        "item": res_data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            except urllib.error.HTTPError as he:
                if he.code == 404:
                    # Session expired or not found on server; recreate and re-send
                    new_session = self.create_omnigent_chat_session(app, agent_name=agent_name, workspace_id=workspace_id)
                    new_session_id = new_session.get("session_id")
                    if new_session_id and new_session_id != session_id:
                        return self.send_build_session_prompt(
                            app, new_session_id, prompt, agent_name=agent_name, workspace_id=workspace_id
                        )
                logger.warning("HTTP error posting prompt to %s (HTTP %s): %s", u, he.code, he)
            except Exception as e:
                logger.warning("Could not post prompt to %s: %s", u, e)

        return {
            "status": "queued",
            "session_id": session_id,
            "prompt": prompt,
            "message": "Prompt dispatched to dev sandbox",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def clear_build_session(self, app, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Reset conversation history by generating a new session for the current workspace."""
        new_session = self.create_omnigent_chat_session(app, workspace_id=workspace_id)
        return new_session


omnigent_dev_service = OmnigentDevService()
