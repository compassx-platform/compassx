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


@router.post("/start")
def start_dev_session(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start or attach to a development sandbox. Pass workspace_id or workspace_name."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    workspace_id = body.workspace_id if body else None
    workspace_name = body.workspace_name if body else None
    host_type = (body.host_type if body and body.host_type else "compassx").lower()
    app_id_val = app.id
    db.expunge(app)
    db.close()

    try:
        unified_reaper_service.touch_app_activity(app_id_val)
        session = omnigent_dev_service.start_dev_session(
            app, workspace_id=workspace_id, workspace_name=workspace_name, host_type=host_type
        )
        return session
    except Exception as e:
        logger.exception("Failed to start dev session for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to start dev session: {str(e)}")


@router.post("/restart")
def restart_dev_sandbox(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Restart dev sandbox: clean up stuck pods/containers and re-provision."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")

    workspace_id = body.workspace_id if body else None
    workspace_name = body.workspace_name if body else None
    host_type = (body.host_type if body and body.host_type else "compassx").lower()
    app_id_val = app.id
    db.expunge(app)
    db.close()

    try:
        unified_reaper_service.touch_app_activity(app_id_val)
        session = omnigent_dev_service.restart_dev_sandbox(
            app, workspace_id=workspace_id, workspace_name=workspace_name, host_type=host_type
        )
        return session
    except Exception as e:
        logger.exception("Failed to restart dev session for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to restart dev session: {str(e)}")


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



