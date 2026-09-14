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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/apps/{app_id}/dev", tags=["Apps Development & Omnigent"])

class ExecCommandRequest(BaseModel):
    command: str
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None

class FileWriteRequest(BaseModel):

    path: str
    content: str

class PublishRequest(BaseModel):
    commit_message: Optional[str] = "Update application via Omnigent Dev Studio"
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None

class CreateSessionRequest(BaseModel):
    agent_name: Optional[str] = "polly"
    title: Optional[str] = None

class StartDevRequest(BaseModel):
    workspace_id: Optional[str] = None  # if provided, resume this workspace; otherwise create new
    workspace_name: Optional[str] = None  # if provided, create or resume workspace with this custom name

class CreateWorkspaceRequest(BaseModel):
    name: str
    git_branch: Optional[str] = None


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
        return omnigent_dev_service.create_dev_workspace(app, name=body.name.strip(), git_branch=body.git_branch)
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
    try:
        session = omnigent_dev_service.start_dev_session(app, workspace_id=workspace_id, workspace_name=workspace_name)
        return session
    except Exception as e:
        logger.exception("Failed to start dev session for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to start dev session: {str(e)}")


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

    return omnigent_dev_service.stop_dev_session(app)


@router.get("/files")
def list_workspace_files(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List source code files in the attached app workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    return omnigent_dev_service.list_workspace_files(app)


@router.get("/file")
def read_workspace_file(
    app_id: str,
    path: str = Query(..., description="Relative file path in workspace"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Read a specific source code file from the app workspace."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    try:
        return omnigent_dev_service.read_workspace_file(app, path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/file")
def write_workspace_file(
    app_id: str,
    body: FileWriteRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save manual code edits to a workspace file (triggering hot reload)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    try:
        return omnigent_dev_service.write_workspace_file(app, body.path, body.content)
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
        raise HTTPException(status_code=500, detail=f"Publish failed: {str(e)}")


@router.post("/workspaces/{workspace_id}/publish")
def publish_workspace_changes(
    app_id: str,
    workspace_id: str,
    body: Optional[PublishRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Commit and push changes for a specific workspace to its dedicated remote Git branch."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    user_id = str(guard.principal.id) if guard.principal else "system"
    commit_msg = body.commit_message if body else None
    try:
        res = omnigent_dev_service.publish_dev_changes(
            app,
            commit_message=commit_msg,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        return res
    except Exception as e:
        logger.exception("Failed to publish workspace %s changes for app %s: %s", workspace_id, app.name, e)
        raise HTTPException(status_code=500, detail=f"Publish failed: {str(e)}")


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
        return omnigent_dev_service.create_omnigent_chat_session(app, agent_name=agent_name, title=title)
    except Exception as e:
        logger.exception("Failed to create Omnigent session for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to create Omnigent session: {str(e)}")


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

    return omnigent_dev_service.get_dev_logs(app, tail=tail)


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

    return dev_terminal_service.exec_command(
        app,
        command=body.command.strip(),
        workspace_id=body.workspace_id,
        workspace_name=body.workspace_name,
    )


@router.websocket("/terminal/ws")
async def dev_terminal_websocket(
    websocket: WebSocket,
    app_id: str,
    token: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    workspace_name: Optional[str] = Query(None),
    cols: int = Query(100),
    rows: int = Query(30),
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

    await dev_terminal_service.handle_terminal_websocket(
        websocket=websocket,
        app=app,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        cols=cols,
        rows=rows,
    )


