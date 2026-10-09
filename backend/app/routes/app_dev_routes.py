import os
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.services.omnigent_dev_service import omnigent_dev_service
from app.services.dev_terminal_service import dev_terminal_service
from app.services.sandbox_reaper_service import unified_reaper_service
from app.sandbox.service import sandbox_service
from app.sandbox.models import SandboxSpec, StorageMount, InitScript, SandboxStatus

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/apps/{app_id}/dev", tags=["Apps Development & Omnigent"])

class ExecCommandRequest(BaseModel):
    command: str
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None

class FileWriteRequest(BaseModel):

    path: str
    content: str
    workspace_id: Optional[str] = None

class PublishRequest(BaseModel):
    commit_message: Optional[str] = "Update application via Omnigent Dev Studio"
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None

class CreateAppSessionRequest(BaseModel):
    agent: str = "opencode"  # 'opencode' | 'pi' | 'antigravity'
    title: Optional[str] = None
    workspace_id: Optional[str] = None
    model: Optional[str] = None

class UpdateAppSessionRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None

class CreateSessionRequest(BaseModel):
    agent_name: Optional[str] = "polly"
    title: Optional[str] = None

class BuildPromptRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    agent_name: Optional[str] = "polly"
    workspace_id: Optional[str] = None

class BuildClearRequest(BaseModel):
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None

class StartDevRequest(BaseModel):
    workspace_id: Optional[str] = None  # if provided, resume this workspace; otherwise create new
    workspace_name: Optional[str] = None  # if provided, create or resume workspace with this custom name
    host_type: Optional[str] = "compassx"  # "compassx" | "omnigent"

class CreateWorkspaceRequest(BaseModel):
    name: str
    git_branch: Optional[str] = None
    base_branch: Optional[str] = "main"
    fetch_remote: Optional[bool] = True

class SyncWorkspaceRequest(BaseModel):
    base_branch: Optional[str] = "main"

class InstallDepsRequest(BaseModel):
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    force: Optional[bool] = False

class VerifyGitRequest(BaseModel):
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None

class RunAppRequest(BaseModel):
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None




@router.get("/workspaces")
def list_dev_workspaces(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all dev workspaces (folders) for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.list_dev_workspaces(app)


@router.post("/workspaces")
def create_dev_workspace(
    app_id: str,
    body: CreateWorkspaceRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new dev workspace folder record for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Workspace name cannot be empty.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        return omnigent_dev_service.create_dev_workspace(
            app,
            name=body.name.strip(),
            git_branch=body.git_branch,
            base_branch=body.base_branch or "main",
            fetch_remote=body.fetch_remote if body.fetch_remote is not None else True,
        )
    except Exception as e:
        logger.exception("Failed to create dev workspace for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to create dev workspace: {str(e)}")


@router.delete("/workspaces/{workspace_id}")
def delete_dev_workspace(
    app_id: str,
    workspace_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a dev workspace folder and its DB record."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    result = omnigent_dev_service.delete_dev_workspace(app, workspace_id)
    if not result.get("deleted") and result.get("reason") == "not_found":
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found.")
    return result


@router.post("/workspaces/{workspace_id}/activate")
def activate_dev_workspace(
    app_id: str,
    workspace_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Instantly switch the active sandbox (git worktree) without restarting container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        return omnigent_dev_service.activate_dev_workspace(app, workspace_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.exception("Failed to activate dev workspace %s for app %s: %s", workspace_id, app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to activate dev workspace: {str(e)}")


@router.post("/workspaces/{workspace_id}/sync-main")
def sync_dev_workspace_with_remote_main(
    app_id: str,
    workspace_id: str,
    body: Optional[SyncWorkspaceRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch remote main and merge it into this sandbox workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    try:
        unified_reaper_service.touch_app_activity(app.id)
        base_branch = (body.base_branch if body and body.base_branch else "main")
        return omnigent_dev_service.sync_workspace_with_remote_main(
            app, workspace_id=workspace_id, base_branch=base_branch
        )
    except Exception as e:
        logger.exception("Failed to sync dev workspace %s with remote main: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to sync with remote main: {str(e)}")


@router.get("/sessions")
def list_app_sessions(
    app_id: str,
    include_archived: bool = Query(False),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all AI agent development sessions for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    from app.services.dev_session_service import dev_session_service
    return dev_session_service.list_sessions(app, include_archived=include_archived)


@router.get("/models")
def list_app_dev_models(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List available AI models for the app's workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    from app.database import AccountSessionLocal
    from app.ai_gateway.models.provider import AIModelEndpoint, AIProvider

    with AccountSessionLocal() as acc_db:
        ws_id = str(app.workspace_id) if app.workspace_id else None
        query = acc_db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)
        if ws_id:
            query = query.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
        endpoints = query.all()

        if not endpoints:
            prov_query = acc_db.query(AIProvider).filter(AIProvider.is_active == True)
            if ws_id:
                prov_query = prov_query.filter((AIProvider.workspace_id == ws_id) | (AIProvider.workspace_id.is_(None)))
            provider = prov_query.first()
            if provider:
                default_models = ["gpt-5.4-mini", "gpt-5.6-sol"]
                seeded = []
                for idx, m_name in enumerate(default_models):
                    ep = AIModelEndpoint(
                        workspace_id=ws_id,
                        name=m_name,
                        provider_id=provider.id,
                        upstream_model_name=m_name,
                        is_active=True,
                        is_default=(idx == 0),
                    )
                    acc_db.add(ep)
                    seeded.append(ep)
                try:
                    acc_db.commit()
                    endpoints = seeded
                except Exception:
                    acc_db.rollback()

        return [
            {
                "id": ep.name,
                "name": ep.name,
                "is_default": ep.is_default,
                "provider": ep.provider.name if ep.provider else "azure",
            }
            for ep in endpoints
        ]


@router.post("/sessions")
def create_app_session(
    app_id: str,
    body: CreateAppSessionRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new development session with a permanently bound agent."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    user_id = str(guard.principal.id) if hasattr(guard, "principal") and getattr(guard.principal, "id", None) else None
    from app.services.dev_session_service import dev_session_service
    return dev_session_service.create_session(
        app=app,
        agent=body.agent,
        title=body.title,
        workspace_id=body.workspace_id,
        user_id=user_id,
        model=body.model,
    )


@router.patch("/sessions/{session_id}")
def update_app_session(
    app_id: str,
    session_id: str,
    body: UpdateAppSessionRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update an app session's title or status (bound agent is strictly immutable)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    from app.services.dev_session_service import dev_session_service
    try:
        return dev_session_service.update_session(
            app=app,
            session_id=session_id,
            title=body.title,
            status=body.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/sessions/{session_id}")
def delete_app_session(
    app_id: str,
    session_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Archive an app session and stop its background tmux process."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    from app.services.dev_session_service import dev_session_service
    return dev_session_service.delete_session(app=app, session_id=session_id)


def _build_app_sandbox_spec(app: App) -> SandboxSpec:
    repo_dir = omnigent_dev_service.get_repo_dir(app)
    clean_k8s_app_id = app.id.replace("_", "-").lower()

    git_url = getattr(app, "git_repo_url", None)
    git_token = None
    if hasattr(app, "git_pat_enc") and app.git_pat_enc:
        try:
            from app.services.encryption import decrypt_field
            git_token = decrypt_field(app.git_pat_enc)
        except Exception:
            pass

    auth_url = git_url or ""
    if git_token and git_url and not ("@" in git_url.split("//")[-1]):
        if "github.com" in git_url:
            auth_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")
        else:
            auth_url = git_url.replace("https://", f"https://oauth2:{git_token}@")

    git_ref = getattr(app, "git_ref", None) or getattr(app, "git_branch", None) or "main"

    clone_cmd = "git status || git init"
    if auth_url:
        clone_cmd = (
            f"if [ ! -d /workspace/.git ] || [ -z \"$(find /workspace -maxdepth 2 -not -name '.git*' -not -name 'index.html' 2>/dev/null)\" ]; then "
            f"  rm -rf /workspace/* /workspace/.[!.]* 2>/dev/null || true; "
            f"  (git clone --branch '{git_ref}' '{auth_url}' /workspace || git clone '{auth_url}' /workspace || (cd /workspace && git init)); "
            f"fi"
        )

    git_config_cmd = "git config --global user.name 'CompassX Dev' && git config --global user.email 'dev@compassx.io'"
    if git_token:
        if "github.com" in (git_url or ""):
            git_config_cmd += f" && git config --global url.\"https://x-access-token:{git_token}@github.com/\".insteadOf \"https://github.com/\""
        elif "gitlab.com" in (git_url or ""):
            git_config_cmd += f" && git config --global url.\"https://oauth2:{git_token}@gitlab.com/\".insteadOf \"https://gitlab.com/\""

    auto_start_script = (
        "python3 -c \""
        "import os, sys, subprocess, yaml, time, socket, threading, re; "
        "manifest = None; "
        "for root, _, files in os.walk('/workspace'):\n"
        "    if 'node_modules' in root or '.git' in root: continue\n"
        "    for f in ('app.yaml', 'app.yml'):\n"
        "        if f in files:\n"
        "            try:\n"
        "                with open(os.path.join(root, f), 'r', encoding='utf-8') as fh:\n"
        "                    manifest = yaml.safe_load(fh)\n"
        "                    manifest['_dir'] = root\n"
        "                    break\n"
        "            except Exception: pass\n"
        "    if manifest: break\n"
        "mdir = manifest.get('_dir', '/workspace') if manifest else '/workspace'\n"
        "services = (manifest.get('services') or {}) if manifest else {}\n"
        "b_cmd = None; b_port = 8000; b_dir = mdir; b_path = '/api'\n"
        "f_cmd = None; f_port = 4000; f_dir = mdir\n"
        "if isinstance(services, dict) and services:\n"
        "    b_svc = services.get('backend') or services.get('api')\n"
        "    if b_svc:\n"
        "        b_cmd = b_svc.get('command') if isinstance(b_svc, dict) else str(b_svc)\n"
        "        if isinstance(b_svc, dict):\n"
        "            b_port = int(b_svc.get('port', 8000))\n"
        "            if b_svc.get('dir'): b_dir = os.path.normpath(os.path.join(mdir, b_svc['dir']))\n"
        "            b_path = b_svc.get('path', '/api')\n"
        "    f_svc = services.get('frontend') or services.get('ui')\n"
        "    if f_svc:\n"
        "        f_cmd = f_svc.get('command') if isinstance(f_svc, dict) else str(f_svc)\n"
        "        if isinstance(f_svc, dict):\n"
        "            f_port = int(f_svc.get('port', 4000))\n"
        "            if f_svc.get('dir'): f_dir = os.path.normpath(os.path.join(mdir, f_svc['dir']))\n"
        "elif manifest and 'command' in manifest:\n"
        "    b_cmd = manifest.get('command')\n"
        "    b_port = int(manifest.get('port', manifest.get('backend_port', 8080)))\n"
        "    if manifest.get('frontend'):\n"
        "        f_cmd = manifest.get('frontend')\n"
        "        f_port = int(manifest.get('frontend_port', 4000))\n"
        "else:\n"
        "    for root, dirs, files in os.walk(mdir):\n"
        "        if 'node_modules' in root or '.git' in root: continue\n"
        "        if not b_cmd and any(f in files for f in ('app.py', 'main.py', 'server.py')):\n"
        "            b_dir = root; b_cmd = 'uvicorn main:app --host 0.0.0.0 --port 8000 --reload' if 'main.py' in files else 'python3 app.py'\n"
        "        if not f_cmd and 'package.json' in files:\n"
        "            f_dir = root; f_cmd = 'npm run dev -- --port 4000 --host 0.0.0.0'\n"
        "for root, _, files in os.walk('/workspace'):\n"
        "    if 'node_modules' in root or '.git' in root: continue\n"
        "    for vf in files:\n"
        "        if vf.startswith('vite.config.') and vf.endswith(('.ts', '.js', '.mjs', '.cjs')):\n"
        "            vp = os.path.join(root, vf)\n"
        "            try:\n"
        "                with open(vp, 'r') as vfh: vc = vfh.read()\n"
        "                if 'allowedHosts' not in vc and 'server:' in vc:\n"
        "                    vc = re.sub(r'server\\\\s*:\\\\s*\\\\{', 'server: {\\\\n    allowedHosts: true,', vc, count=1)\n"
        "                    with open(vp, 'w') as vfh: vfh.write(vc)\n"
        "            except Exception: pass\n"
        "if b_cmd:\n"
        "    b_str = ' '.join(b_cmd) if isinstance(b_cmd, list) else str(b_cmd)\n"
        "    subprocess.Popen(b_str, shell=True, cwd=b_dir, stdout=open('/tmp/app_backend.log', 'a'), stderr=subprocess.STDOUT)\n"
        "if f_cmd:\n"
        "    f_str = ' '.join(f_cmd) if isinstance(f_cmd, list) else str(f_cmd)\n"
        "    subprocess.Popen(f_str, shell=True, cwd=f_dir, stdout=open('/tmp/app_frontend.log', 'a'), stderr=subprocess.STDOUT)\n"
        "time.sleep(0.5)\n"
        "GATEWAY_PORT = 8080\n"
        "SPLASH_HTML = b'HTTP/1.1 200 OK\\\\r\\\\nContent-Type: text/html; charset=utf-8\\\\r\\\\nConnection: close\\\\r\\\\n\\\\r\\\\n<!DOCTYPE html><html><head><meta charset=\"utf-8\"><meta http-equiv=\"refresh\" content=\"2\"><title>Live Sandbox Starting</title><style>body{background:#0b0f19;color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}.card{background:#111827;border:1px solid #1e293b;border-radius:12px;padding:2.5rem;text-align:center;max-width:440px;box-shadow:0 20px 25px -5px rgba(0,0,0,0.5);}.spinner{width:38px;height:38px;border:3px solid rgba(59,130,246,0.2);border-top-color:#3b82f6;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 1.25rem;}@keyframes spin{to{transform:rotate(360deg);}}h2{font-size:1.2rem;font-weight:600;margin-bottom:0.5rem;color:#f8fafc;}p{font-size:0.875rem;color:#94a3b8;line-height:1.5;}</style></head><body><div class=\"card\"><div class=\"spinner\"></div><h2>Live Sandbox Starting...</h2><p>Application dev server is compiling and starting. This preview will automatically refresh once ready.</p></div></body></html>'\n"
        "def forward(src, dst):\n"
        "    while True:\n"
        "        try:\n"
        "            data = src.recv(8192)\n"
        "            if not data: break\n"
        "            dst.sendall(data)\n"
        "        except Exception: break\n"
        "    try: src.close()\n"
        "    except Exception: pass\n"
        "    try: dst.close()\n"
        "    except Exception: pass\n"
        "def handle_client(client):\n"
        "    try:\n"
        "        peek = client.recv(1024, socket.MSG_PEEK)\n"
        "        t_port = f_port if f_cmd else b_port\n"
        "        if peek and f_cmd and b_cmd:\n"
        "            try:\n"
        "                line = peek.decode('utf-8', errors='ignore').split('\\\\r\\\\n')[0]\n"
        "                parts = line.split(' ')\n"
        "                if len(parts) >= 2:\n"
        "                    path = parts[1]\n"
        "                    if path.startswith(b_path) or path.startswith('/ws') or path.startswith('/docs') or path.startswith('/openapi.json'):\n"
        "                        t_port = b_port\n"
        "                    else:\n"
        "                        t_port = f_port\n"
        "            except Exception: pass\n"
        "        try:\n"
        "            target = socket.create_connection(('127.0.0.1', int(t_port)), timeout=3)\n"
        "            threading.Thread(target=forward, args=(client, target), daemon=True).start()\n"
        "            threading.Thread(target=forward, args=(target, client), daemon=True).start()\n"
        "        except Exception:\n"
        "            try:\n"
        "                client.sendall(SPLASH_HTML)\n"
        "                client.close()\n"
        "            except Exception: pass\n"
        "    except Exception:\n"
        "        try: client.close()\n"
        "        except Exception: pass\n"
        "srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        "srv.bind(('0.0.0.0', GATEWAY_PORT))\n"
        "srv.listen(100)\n"
        "while True:\n"
        "    try:\n"
        "        c, _ = srv.accept()\n"
        "        threading.Thread(target=handle_client, args=(c,), daemon=True).start()\n"
        "    except Exception: pass\n"
        "\" > /tmp/auto_start.log 2>&1 &"
    )

    auth_sync_script = (
        "mkdir -p /root/.gemini/antigravity-cli /root/.gemini/config /workspace/.gemini_auth/antigravity-cli /workspace/.gemini_auth/config 2>/dev/null || true; "
        "if [ -d /workspaces/.shared_auth/.gemini ] && [ -n \"$(find /workspaces/.shared_auth/.gemini -type f 2>/dev/null)\" ]; then "
        "  cp -rn /workspaces/.shared_auth/.gemini/* /root/.gemini/ 2>/dev/null || true; "
        "  cp -rn /workspaces/.shared_auth/.gemini/* /workspace/.gemini_auth/ 2>/dev/null || true; "
        "elif [ -d /workspace/.gemini_auth ] && [ -n \"$(find /workspace/.gemini_auth -type f 2>/dev/null)\" ]; then "
        "  cp -rn /workspace/.gemini_auth/* /root/.gemini/ 2>/dev/null || true; "
        "  if [ -d /workspaces ]; then "
        "    mkdir -p /workspaces/.shared_auth/.gemini 2>/dev/null || true; "
        "    cp -rn /workspace/.gemini_auth/* /workspaces/.shared_auth/.gemini/ 2>/dev/null || true; "
        "  fi; "
        "fi; "
        "(while true; do "
        "  for src in /root/.gemini /root/.omnigent/antigravity-native/*/agy-home/.gemini; do "
        "    if [ -d \"$src\" ]; then "
        "      for f in antigravity-cli/antigravity-oauth-token oauth_creds.json antigravity-cli/jetski_state.pbtxt antigravity-cli/installation_id config/config.json config/projects/default-cli-project.json config/mcp_config.json; do "
        "        if [ -f \"$src/$f\" ] && [ -s \"$src/$f\" ]; then "
        "          mkdir -p \"/workspace/.gemini_auth/$(dirname \"$f\")\" 2>/dev/null || true; "
        "          cp -u \"$src/$f\" \"/workspace/.gemini_auth/$f\" 2>/dev/null || cp -f \"$src/$f\" \"/workspace/.gemini_auth/$f\" 2>/dev/null || true; "
        "          if [ -d /workspaces/.shared_auth/.gemini ]; then "
        "            mkdir -p \"/workspaces/.shared_auth/.gemini/$(dirname \"$f\")\" 2>/dev/null || true; "
        "            cp -u \"$src/$f\" \"/workspaces/.shared_auth/.gemini/$f\" 2>/dev/null || cp -f \"$src/$f\" \"/workspaces/.shared_auth/.gemini/$f\" 2>/dev/null || true; "
        "          fi; "
        "        fi; "
        "      done; "
        "    fi; "
        "  done; "
        "  sleep 3; "
        "done) &"
    )

    return SandboxSpec(
        sandbox_id=f"dev-app-{app.id}",
        consumer_key=f"app_{app.id}",
        name=f"{app.name} (Dev Sandbox)",
        consumer_module="app",
        workspace_id=str(app.workspace_id) if app.workspace_id else None,
        image=os.environ.get("COMPASSX_SANDBOX_IMAGE") or "ghcr.io/omnigent-ai/omnigent-host:latest",
        ports=[8080, 9201],
        storage_mounts=[StorageMount(source_path=repo_dir, mount_path="/workspace")],
        init_scripts=[
            InitScript(name="Restore & Sync Agent Auth", command=auth_sync_script, ignore_failure=True),
            InitScript(name="Configure Git Credentials", command=git_config_cmd, ignore_failure=True),
            InitScript(name="Prepare Workspace Code", command=clone_cmd, ignore_failure=True),
            InitScript(name="Install Dependencies", command="pip install -r requirements.txt || (find /workspace -maxdepth 3 -name package.json -execdir npm install \\; 2>/dev/null) || true", timeout_seconds=180, ignore_failure=True),
            InitScript(name="Run Application Server", command=auto_start_script, ignore_failure=True),
        ],
        labels={
            "compassx/app-id": clean_k8s_app_id,
            "compassx/dev": "true",
            "compassx/role": "dev",
            "compassx-app-id": app.id,
            "compassx.app_id": app.id,
            "compassx.app_slug": app.slug or "",
            "compassx.consumer_key": f"app_{app.id}",
            "compassx-consumer-key": f"app_{app.id}",
        },
        metadata={"app_id": app.id, "app_name": app.name, "slug": app.slug},
    )


@router.post("/start")
def start_dev_session(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start or attach to a development sandbox via the centralized Sandbox engine."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    unified_reaper_service.touch_app_activity(app.id)
    spec = _build_app_sandbox_spec(app)
    instance = sandbox_service.ensure_sandbox(spec)
    return {
        "app_id": app.id,
        "status": "active" if instance.status in (SandboxStatus.READY, SandboxStatus.RUNNING) else str(instance.status.value),
        "mode": instance.runtime_mode,
        "container_id": instance.container_id,
        "dev_port": instance.ports[0] if instance.ports else 8080,
        "endpoints": instance.endpoints,
        "sandbox_id": instance.id,
    }


@router.post("/restart")
def restart_dev_sandbox(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Restart dev sandbox: cleanly terminate and re-ensure compute via Sandbox engine."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    unified_reaper_service.touch_app_activity(app.id)

    try:
        sandbox_service.terminate_sandbox(f"dev-app-{app.id}")
    except Exception as e:
        logger.debug("Restart termination error for dev-app-%s: %s", app.id, e)

    spec = _build_app_sandbox_spec(app)
    instance = sandbox_service.ensure_sandbox(spec)
    return {
        "app_id": app.id,
        "status": "active" if instance.status in (SandboxStatus.READY, SandboxStatus.RUNNING) else str(instance.status.value),
        "mode": instance.runtime_mode,
        "container_id": instance.container_id,
        "dev_port": instance.ports[0] if instance.ports else 8080,
        "endpoints": instance.endpoints,
        "sandbox_id": instance.id,
    }


@router.post("/sandbox/ensure")
def ensure_app_sandbox(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Idempotently ensure dev sandbox is running for this app, returning live progress or ready instance."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    unified_reaper_service.touch_app_activity(app.id)
    spec = _build_app_sandbox_spec(app)
    instance = sandbox_service.ensure_sandbox(spec)
    return instance


@router.get("/sandbox/status")
def get_app_sandbox_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get active sandbox and detailed stage progress for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    unified_reaper_service.touch_app_activity(app.id)
    instance = sandbox_service.find_active_sandbox(
        sandbox_id=f"dev-app-{app.id}",
        consumer_key=f"app_{app.id}",
        consumer_module="app",
    )
    if instance:
        instance = sandbox_service.get_sandbox(instance.id)
        return instance
    return {
        "id": f"dev-app-{app.id}",
        "consumer_key": f"app_{app.id}",
        "name": f"{app.name} (Dev Sandbox)",
        "consumer_module": "app",
        "status": "stopped",
        "endpoints": {},
        "progress": None,
    }


@router.get("/status")
def get_dev_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Check status of active development sandbox and Databricks Omnigent server."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.get_dev_session(app)



@router.post("/stop")
def stop_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop the development sandbox container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    db.expunge(app)
    db.close()

    # 1. Terminate sandbox instance in centralized sandbox_service
    try:
        sandbox_service.terminate_sandbox(f"dev-app-{app.id}")
    except Exception as sb_err:
        logger.debug("Sandbox terminate error for dev-app-%s: %s", app.id, sb_err)

    try:
        active_sb = sandbox_service.find_active_sandbox(consumer_key=f"app_{app.id}")
        if active_sb:
            sandbox_service.terminate_sandbox(active_sb.id)
    except Exception as sb_err2:
        logger.debug("Sandbox terminate error for consumer app_%s: %s", app.id, sb_err2)

    # 2. Stop legacy dev session
    return omnigent_dev_service.stop_dev_session(app)


@router.post("/suspend")
def suspend_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Suspend dev sandbox (scale compute to 0 replicas, keep storage intact)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    db.expunge(app)
    db.close()

    try:
        sandbox_service.suspend_sandbox(f"dev-app-{app.id}")
    except Exception:
        pass

    try:
        active_sb = sandbox_service.find_active_sandbox(consumer_key=f"app_{app.id}")
        if active_sb:
            sandbox_service.suspend_sandbox(active_sb.id)
    except Exception:
        pass

    return omnigent_dev_service.suspend_dev_session(app)


@router.post("/resume")
def resume_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Resume a suspended dev sandbox (restore compute to 1 replica)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)

    try:
        sandbox_service.resume_sandbox(f"dev-app-{app.id}")
    except Exception:
        pass

    try:
        active_sb = sandbox_service.find_active_sandbox(consumer_key=f"app_{app.id}")
        if active_sb:
            sandbox_service.resume_sandbox(active_sb.id)
    except Exception:
        pass

    return omnigent_dev_service.resume_dev_session(app)


@router.get("/files")
def list_workspace_files(
    app_id: str,
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List source code files in the attached app workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.list_workspace_files(app, workspace_id=workspace_id)



@router.get("/file")
def read_workspace_file(
    app_id: str,
    path: str = Query(..., description="Relative file path in workspace"),
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Read a specific source code file from the app workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    try:
        unified_reaper_service.touch_app_activity(app.id)
        return omnigent_dev_service.read_workspace_file(app, path, workspace_id=workspace_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/file")
def write_workspace_file(
    app_id: str,
    body: FileWriteRequest,
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save manual code edits to a workspace file (triggering hot reload)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    try:
        unified_reaper_service.touch_app_activity(app.id)
        target_ws = body.workspace_id or workspace_id
        return omnigent_dev_service.write_workspace_file(app, body.path, body.content, workspace_id=target_ws)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publish")
def publish_dev_changes(
    app_id: str,
    body: Optional[PublishRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Commit workspace changes and push to its dedicated remote Git branch."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    user_id = str(guard.principal.id) if guard.principal else "system"
    commit_msg = body.commit_message if body else None
    ws_id = body.workspace_id if body else None
    ws_name = body.workspace_name if body else None
    try:
        unified_reaper_service.touch_app_activity(app.id)
        res = omnigent_dev_service.publish_dev_changes(
            app,
            commit_message=commit_msg,
            user_id=user_id,
            workspace_id=ws_id,
            workspace_name=ws_name,
        )
        return res
    except Exception as e:
        logger.exception("Failed to publish dev changes for app %s: %s", app.name, e)
@router.get("/commits")
def get_git_commits(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    workspace_name: Optional[str] = Query(None),
    limit: Optional[int] = Query(50),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve Git commit history for the application workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)

    return omnigent_dev_service.get_git_commits(
        app=app,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        limit=limit or 50,
    )


@router.get("/workspaces/{workspace_id}/commits")
def get_workspace_git_commits(
    app_id: str,
    workspace_id: str,
    limit: Optional[int] = Query(50),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve Git commit history for a specific workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)

    return omnigent_dev_service.get_git_commits(
        app=app,
        workspace_id=workspace_id,
        limit=limit or 50,
    )


@router.get("/omnigent/agents")
def get_omnigent_agents(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch available AI agents from Databricks Omnigent server."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.get_omnigent_agents()


@router.post("/omnigent/session")
def create_omnigent_session(
    app_id: str,
    body: Optional[CreateSessionRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new conversational AI session on Omnigent Server bound to the app host."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    agent_name = body.agent_name if body else "polly"
    title = body.title if body else None
    try:
        unified_reaper_service.touch_app_activity(app.id)
        return omnigent_dev_service.create_omnigent_chat_session(app, agent_name=agent_name, title=title)
    except Exception as e:
        logger.exception("Failed to create Omnigent session for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to create Omnigent session: {str(e)}")


@router.get("/build/session")
def get_build_session(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get or initialize the active Build Studio AI session for this app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.get_build_session(app, workspace_id=workspace_id)


@router.get("/build/messages")
def get_build_session_messages(
    app_id: str,
    session_id: str = Query(...),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get chat transcript items for the specified Build Studio session."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.get_build_session_messages(app, session_id=session_id)


@router.post("/build/prompt")
def send_build_prompt(
    app_id: str,
    body: BuildPromptRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Send an AI coding instruction / prompt to the Build Studio session."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    if not body.prompt or not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    unified_reaper_service.touch_app_activity(app.id)
    session_id = body.session_id
    if not session_id:
        sess = omnigent_dev_service.get_build_session(app, workspace_id=body.workspace_id)
        session_id = sess.get("session_id")

    return omnigent_dev_service.send_build_session_prompt(
        app,
        session_id=session_id,
        prompt=body.prompt.strip(),
        agent_name=body.agent_name,
        workspace_id=body.workspace_id,
    )


@router.post("/build/clear")
def clear_build_session(
    app_id: str,
    body: Optional[BuildClearRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Clear Build Studio session history and start fresh conversation."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    ws_id = body.workspace_id if body else None
    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.clear_build_session(app, workspace_id=ws_id)


@router.get("/logs")
def get_dev_sandbox_logs(
    app_id: str,
    tail: int = Query(100, description="Number of tail log lines"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch real-time stdout/stderr runtime logs from the dev sandbox container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.get_dev_logs(app, tail=tail)


@router.post("/verify-git")
def verify_git_workspace(
    app_id: str,
    body: Optional[VerifyGitRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Verify git status, branch, and working tree for dev workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    workspace_id = body.workspace_id if body else None
    workspace_name = body.workspace_name if body else None

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.verify_git_workspace(
        app, workspace_id=workspace_id, workspace_name=workspace_name
    )


@router.post("/install-deps")
def install_dev_dependencies(
    app_id: str,
    body: Optional[InstallDepsRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Verify and install dependencies (pip / npm) inside active dev sandbox."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    workspace_id = body.workspace_id if body else None
    workspace_name = body.workspace_name if body else None
    force = body.force if body else False

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.install_dev_dependencies(
        app, workspace_id=workspace_id, workspace_name=workspace_name, force=force
    )


@router.post("/run-app")
def run_dev_application(
    app_id: str,
    body: Optional[RunAppRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start application dev processes (FastAPI / Vite) and verify local runtime."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    workspace_id = body.workspace_id if body else None
    workspace_name = body.workspace_name if body else None

    app_id_val = app.id
    db.expunge(app)
    db.close()

    unified_reaper_service.touch_app_activity(app_id_val)
    return omnigent_dev_service.run_dev_app(
        app, workspace_id=workspace_id, workspace_name=workspace_name
    )



@router.post("/exec")
def exec_dev_command(
    app_id: str,
    body: ExecCommandRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Execute a single shell command inside the dev sandbox container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    if not body.command or not body.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty.")

    unified_reaper_service.touch_app_activity(app.id)
    return dev_terminal_service.exec_command(
        app,
        command=body.command.strip(),
        workspace_id=body.workspace_id,
        workspace_name=body.workspace_name,
    )


@router.post("/heartbeat")
def record_dev_heartbeat(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Client heartbeat endpoint to keep active dev session and workspace alive."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    unified_reaper_service.touch_app_activity(app.id)
    return {"status": "ok", "app_id": app.id}


@router.websocket("/terminal/ws")
async def dev_terminal_websocket(
    websocket: WebSocket,
    app_id: str,
    token: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    workspace_name: Optional[str] = Query(None),
    cols: int = Query(100),
    rows: int = Query(30),
    agent: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """Interactive real-time WebSocket terminal inside the dev pod/container."""
    from app.database import SystemSessionLocal
    with SystemSessionLocal() as db:
        app = db.query(App).filter(App.id == app_id).first()
        if not app:
            await websocket.accept()
            await websocket.send_text(f"\r\n\x1b[1;31mApp '{app_id}' not found.\x1b[0m\r\n")
            await websocket.close(code=4404, reason=f"App '{app_id}' not found")
            return

    unified_reaper_service.touch_app_activity(app.id)
    await dev_terminal_service.handle_terminal_websocket(
        websocket=websocket,
        app=app,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        cols=cols,
        rows=rows,
        agent=agent,
        session_id=session_id,
    )


class AppManifestUpdateRequest(BaseModel):
    frontend_command: Optional[str] = None
    frontend_dir: Optional[str] = None
    frontend_port: Optional[int] = None
    backend_command: Optional[str] = None
    backend_dir: Optional[str] = None
    backend_port: Optional[int] = None
    install_command: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    raw_yaml: Optional[str] = None
    workspace_id: Optional[str] = None


@router.get("/manifest")
def get_dev_manifest(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve and parse the app.yaml manifest or generated runtime configuration for an app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    repo_dir = omnigent_dev_service.get_repo_dir(app)
    manifest = app_manifest_service.load_manifest(repo_dir)
    if not manifest:
        try:
            from app.services.drivers.factory import driver_factory
            dev_driver = driver_factory.get_dev_driver()
            clean_id = app.id.replace("_", "-").lower()
            manifest = omnigent_dev_service._resolve_app_manifest(app, dev_driver, f"{clean_id}/default", repo_dir, repo_dir)
        except Exception:
            pass
    run_cfg = app_manifest_service.get_run_config(manifest)
    return {
        "app_id": app.id,
        "has_manifest": manifest is not None,
        "manifest": manifest,
        "run_config": run_cfg or {
            "gateway_port": 8080,
            "frontend_port": 4000,
            "backend_port": 8000,
            "frontend_command": "npm run dev",
            "backend_command": "uvicorn main:app --port 8000",
        },
    }


@router.put("/manifest")
def update_dev_manifest(
    app_id: str,
    body: AppManifestUpdateRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save or generate an app.yaml manifest directly into the app repository."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    repo_dir = omnigent_dev_service.get_repo_dir(app)
    os.makedirs(repo_dir, exist_ok=True)
    manifest_path = os.path.join(repo_dir, "app.yaml")

    if body.raw_yaml and body.raw_yaml.strip():
        yaml_content = body.raw_yaml.strip()
    else:
        manifest_dict: Dict[str, Any] = {
            "version": "1",
            "name": app.slug or app.name or app.id,
            "services": {}
        }
        if body.backend_command:
            manifest_dict["services"]["backend"] = {
                "command": body.backend_command,
                "port": body.backend_port or 8000,
                "dir": body.backend_dir or ".",
                "path": "/api",
            }
        if body.frontend_command:
            manifest_dict["services"]["frontend"] = {
                "command": body.frontend_command,
                "port": body.frontend_port or 4000,
                "dir": body.frontend_dir or "frontend",
                "path": "/",
            }
        if body.install_command:
            manifest_dict["install"] = body.install_command
        if body.env:
            manifest_dict["env"] = body.env

        yaml_content = yaml.dump(manifest_dict, sort_keys=False, default_flow_style=False)

    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
    except Exception:
        pass

    # Sync to dev sandbox pod if running
    try:
        from app.services.drivers.factory import driver_factory
        import base64
        dev_driver = driver_factory.get_dev_driver()
        clean_id = app.id.replace("_", "-").lower()
        b64 = base64.b64encode(yaml_content.encode("utf-8")).decode("ascii")
        sync_cmd = f"mkdir -p /workspace && echo '{b64}' | base64 -d | tee /workspace/app.yaml /workspaces/{clean_id}/*/app.yaml 2>/dev/null || true"
        dev_driver.exec_command_in_dev(app, sync_cmd)
    except Exception:
        pass

    parsed = app_manifest_service.parse_manifest_text(yaml_content, manifest_path=manifest_path)
    run_cfg = app_manifest_service.get_run_config(parsed)

    return {
        "app_id": app.id,
        "status": "saved",
        "manifest_path": manifest_path,
        "manifest": parsed,
        "run_config": run_cfg,
    }



