
import os
import base64
import logging
import yaml
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from app.database import get_system_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.services.app_manifest_service import app_manifest_service
from app.services.omnigent_dev_service import omnigent_dev_service
from app.services.studio.workspace_files import get_workspace_file_service
from app.services.dev_terminal_service import dev_terminal_service
from app.services.sandbox_reaper_service import unified_reaper_service
from app.sandbox.service import sandbox_service
from app.sandbox.models import SandboxSpec, StorageMount, InitScript, SandboxStatus

import app.apps.dev.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.apps.dev.application.list_dev_workspaces import list_dev_workspaces as list_dev_workspaces_action
from app.apps.dev.application.create_dev_workspace import create_dev_workspace as create_dev_workspace_action
from app.apps.dev.application.delete_dev_workspace import delete_dev_workspace as delete_dev_workspace_action
from app.apps.dev.application.activate_dev_workspace import activate_dev_workspace as activate_dev_workspace_action
from app.apps.dev.application.sync_dev_workspace_with_remote_main import sync_dev_workspace_with_remote_main as sync_dev_workspace_with_remote_main_action
from app.apps.dev.application.list_app_sessions import list_app_sessions as list_app_sessions_action
from app.apps.dev.application.list_app_dev_models import list_app_dev_models as list_app_dev_models_action
from app.apps.dev.application.create_app_session import create_app_session as create_app_session_action
from app.apps.dev.application.update_app_session import update_app_session as update_app_session_action
from app.apps.dev.application.delete_app_session import delete_app_session as delete_app_session_action
from app.apps.dev.application.start_dev_session import start_dev_session as start_dev_session_action
from app.apps.dev.application.restart_dev_sandbox import restart_dev_sandbox as restart_dev_sandbox_action
from app.apps.dev.application.ensure_app_sandbox import ensure_app_sandbox as ensure_app_sandbox_action
from app.apps.dev.application.get_app_sandbox_status import get_app_sandbox_status as get_app_sandbox_status_action
from app.apps.dev.application.get_dev_status import get_dev_status as get_dev_status_action
from app.apps.dev.application.stop_dev_session import stop_dev_session as stop_dev_session_action
from app.apps.dev.application.suspend_dev_session import suspend_dev_session as suspend_dev_session_action
from app.apps.dev.application.resume_dev_session import resume_dev_session as resume_dev_session_action
from app.apps.dev.application.list_workspace_files import list_workspace_files as list_workspace_files_action
from app.apps.dev.application.read_workspace_file import read_workspace_file as read_workspace_file_action
from app.apps.dev.application.diff_workspace_file import diff_workspace_file as diff_workspace_file_action
from app.apps.dev.application.write_workspace_file import write_workspace_file as write_workspace_file_action
from app.apps.dev.application.publish_dev_changes import publish_dev_changes as publish_dev_changes_action
from app.apps.dev.application.get_git_commits import get_git_commits as get_git_commits_action
from app.apps.dev.application.get_workspace_git_commits import get_workspace_git_commits as get_workspace_git_commits_action
from app.apps.dev.application.get_omnigent_agents import get_omnigent_agents as get_omnigent_agents_action
from app.apps.dev.application.create_omnigent_session import create_omnigent_session as create_omnigent_session_action
from app.apps.dev.application.get_build_session import get_build_session as get_build_session_action
from app.apps.dev.application.get_build_session_messages import get_build_session_messages as get_build_session_messages_action
from app.apps.dev.application.send_build_prompt import send_build_prompt as send_build_prompt_action
from app.apps.dev.application.clear_build_session import clear_build_session as clear_build_session_action
from app.apps.dev.application.get_dev_sandbox_logs import get_dev_sandbox_logs as get_dev_sandbox_logs_action
from app.apps.dev.application.verify_git_workspace import verify_git_workspace as verify_git_workspace_action
from app.apps.dev.application.install_dev_dependencies import install_dev_dependencies as install_dev_dependencies_action
from app.apps.dev.application.run_dev_application import run_dev_application as run_dev_application_action
from app.apps.dev.application.exec_dev_command import exec_dev_command as exec_dev_command_action
from app.apps.dev.application.record_dev_heartbeat import record_dev_heartbeat as record_dev_heartbeat_action
from app.apps.dev.application.dev_terminal_websocket import dev_terminal_websocket as dev_terminal_websocket_action
from app.apps.dev.application.get_dev_manifest import get_dev_manifest as get_dev_manifest_action
from app.apps.dev.application.update_dev_manifest import update_dev_manifest as update_dev_manifest_action

router = APIRouter(prefix="/api/v1/apps/{app_id}/dev", tags=["Apps Development & Omnigent"])

@router.get("/workspaces")
def list_dev_workspaces(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all dev workspaces (folders) for this app."""
    return list_dev_workspaces_action(app_id=app_id, db=db, guard=guard)

@router.post("/workspaces")
def create_dev_workspace(
    app_id: str,
    body: CreateWorkspaceRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new dev workspace folder record for this app."""
    return create_dev_workspace_action(app_id=app_id, body=body, db=db, guard=guard)

@router.delete("/workspaces/{workspace_id}")
def delete_dev_workspace(
    app_id: str,
    workspace_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Delete a dev workspace folder and its DB record."""
    return delete_dev_workspace_action(app_id=app_id, workspace_id=workspace_id, db=db, guard=guard)

@router.post("/workspaces/{workspace_id}/activate")
def activate_dev_workspace(
    app_id: str,
    workspace_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Instantly switch the active sandbox (git worktree) without restarting container."""
    return activate_dev_workspace_action(app_id=app_id, workspace_id=workspace_id, db=db, guard=guard)

@router.post("/workspaces/{workspace_id}/sync-main")
def sync_dev_workspace_with_remote_main(
    app_id: str,
    workspace_id: str,
    body: Optional[SyncWorkspaceRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch remote main and merge it into this sandbox workspace."""
    return sync_dev_workspace_with_remote_main_action(app_id=app_id, workspace_id=workspace_id, body=body, db=db, guard=guard)

@router.get("/sessions")
def list_app_sessions(
    app_id: str,
    include_archived: bool = Query(False),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all AI agent development sessions for this app."""
    return list_app_sessions_action(app_id=app_id, include_archived=include_archived, db=db, guard=guard)

@router.get("/models")
def list_app_dev_models(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List available AI models for the app's workspace."""
    return list_app_dev_models_action(app_id=app_id, db=db, guard=guard)

@router.post("/sessions")
def create_app_session(
    app_id: str,
    body: CreateAppSessionRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new development session with a permanently bound agent."""
    return create_app_session_action(app_id=app_id, body=body, db=db, guard=guard)

@router.patch("/sessions/{session_id}")
def update_app_session(
    app_id: str,
    session_id: str,
    body: UpdateAppSessionRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update an app session's title or status (bound agent is strictly immutable)."""
    return update_app_session_action(app_id=app_id, session_id=session_id, body=body, db=db, guard=guard)

@router.delete("/sessions/{session_id}")
def delete_app_session(
    app_id: str,
    session_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Archive an app session and stop its background tmux process."""
    return delete_app_session_action(app_id=app_id, session_id=session_id, db=db, guard=guard)

@router.post("/start")
def start_dev_session(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start or attach to a development sandbox via the centralized Sandbox engine."""
    return start_dev_session_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/restart")
def restart_dev_sandbox(
    app_id: str,
    body: Optional[StartDevRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Restart dev sandbox: cleanly terminate and re-ensure compute via Sandbox engine."""
    return restart_dev_sandbox_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/sandbox/ensure")
def ensure_app_sandbox(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Idempotently ensure dev sandbox is running for this app, returning live progress or ready instance."""
    return ensure_app_sandbox_action(app_id=app_id, db=db, guard=guard)

@router.get("/sandbox/status")
def get_app_sandbox_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get active sandbox and detailed stage progress for this app."""
    return get_app_sandbox_status_action(app_id=app_id, db=db, guard=guard)

@router.get("/status")
def get_dev_status(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Check status of active development sandbox and Databricks Omnigent server."""
    return get_dev_status_action(app_id=app_id, db=db, guard=guard)

@router.post("/stop")
def stop_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Stop the development sandbox container."""
    return stop_dev_session_action(app_id=app_id, db=db, guard=guard)

@router.post("/suspend")
def suspend_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Suspend dev sandbox (scale compute to 0 replicas, keep storage intact)."""
    return suspend_dev_session_action(app_id=app_id, db=db, guard=guard)

@router.post("/resume")
def resume_dev_session(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Resume a suspended dev sandbox (restore compute to 1 replica)."""
    return resume_dev_session_action(app_id=app_id, db=db, guard=guard)

@router.get("/files")
def list_workspace_files(
    app_id: str,
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List source code files in the attached app workspace."""
    return list_workspace_files_action(app_id=app_id, workspace_id=workspace_id, db=db, guard=guard)

@router.get("/file")
def read_workspace_file(
    app_id: str,
    path: str = Query(..., description="Relative file path in workspace"),
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Read a specific source code file from the app workspace."""
    return read_workspace_file_action(app_id=app_id, path=path, workspace_id=workspace_id, db=db, guard=guard)

@router.get("/file/diff")
def diff_workspace_file(
    app_id: str,
    path: str = Query(..., description="Relative file path in workspace"),
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Unified diff of one sandbox file against the last commit."""
    return diff_workspace_file_action(app_id=app_id, path=path, workspace_id=workspace_id, db=db, guard=guard)

@router.put("/file")
def write_workspace_file(
    app_id: str,
    body: FileWriteRequest,
    workspace_id: Optional[str] = Query(None, description="Active sandbox workspace ID or name"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save manual code edits to a workspace file (triggering hot reload)."""
    return write_workspace_file_action(app_id=app_id, body=body, workspace_id=workspace_id, db=db, guard=guard)

@router.post("/publish")
def publish_dev_changes(
    app_id: str,
    body: Optional[PublishRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Commit workspace changes and push to its dedicated remote Git branch."""
    return publish_dev_changes_action(app_id=app_id, body=body, db=db, guard=guard)

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
    return get_git_commits_action(app_id=app_id, workspace_id=workspace_id, workspace_name=workspace_name, limit=limit, db=db, guard=guard)

@router.get("/workspaces/{workspace_id}/commits")
def get_workspace_git_commits(
    app_id: str,
    workspace_id: str,
    limit: Optional[int] = Query(50),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve Git commit history for a specific workspace."""
    return get_workspace_git_commits_action(app_id=app_id, workspace_id=workspace_id, limit=limit, db=db, guard=guard)

@router.get("/omnigent/agents")
def get_omnigent_agents(
    app_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch available AI agents from Databricks Omnigent server."""
    return get_omnigent_agents_action(app_id=app_id, db=db, guard=guard)

@router.post("/omnigent/session")
def create_omnigent_session(
    app_id: str,
    body: Optional[CreateSessionRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new conversational AI session on Omnigent Server bound to the app host."""
    return create_omnigent_session_action(app_id=app_id, body=body, db=db, guard=guard)

@router.get("/build/session")
def get_build_session(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get or initialize the active Build Studio AI session for this app."""
    return get_build_session_action(app_id=app_id, workspace_id=workspace_id, db=db, guard=guard)

@router.get("/build/messages")
def get_build_session_messages(
    app_id: str,
    session_id: str = Query(...),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get chat transcript items for the specified Build Studio session."""
    return get_build_session_messages_action(app_id=app_id, session_id=session_id, db=db, guard=guard)

@router.post("/build/prompt")
def send_build_prompt(
    app_id: str,
    body: BuildPromptRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Send an AI coding instruction / prompt to the Build Studio session."""
    return send_build_prompt_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/build/clear")
def clear_build_session(
    app_id: str,
    body: Optional[BuildClearRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Clear Build Studio session history and start fresh conversation."""
    return clear_build_session_action(app_id=app_id, body=body, db=db, guard=guard)

@router.get("/logs")
def get_dev_sandbox_logs(
    app_id: str,
    tail: int = Query(100, description="Number of tail log lines"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Fetch real-time stdout/stderr runtime logs from the dev sandbox container."""
    return get_dev_sandbox_logs_action(app_id=app_id, tail=tail, db=db, guard=guard)

@router.post("/verify-git")
def verify_git_workspace(
    app_id: str,
    body: Optional[VerifyGitRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Verify git status, branch, and working tree for dev workspace."""
    return verify_git_workspace_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/install-deps")
def install_dev_dependencies(
    app_id: str,
    body: Optional[InstallDepsRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Verify and install dependencies (pip / npm) inside active dev sandbox."""
    return install_dev_dependencies_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/run-app")
def run_dev_application(
    app_id: str,
    body: Optional[RunAppRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Start application dev processes (FastAPI / Vite) and verify local runtime."""
    return run_dev_application_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/exec")
def exec_dev_command(
    app_id: str,
    body: ExecCommandRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Execute a single shell command inside the dev sandbox container."""
    return exec_dev_command_action(app_id=app_id, body=body, db=db, guard=guard)

@router.post("/heartbeat")
def record_dev_heartbeat(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Client heartbeat endpoint to keep active dev session and workspace alive."""
    return record_dev_heartbeat_action(app_id=app_id, workspace_id=workspace_id, db=db, guard=guard)

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
    return await dev_terminal_websocket_action(websocket=websocket, app_id=app_id, token=token, workspace_id=workspace_id, workspace_name=workspace_name, cols=cols, rows=rows, agent=agent, session_id=session_id)

@router.get("/manifest")
def get_dev_manifest(
    app_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve and parse the app.yaml manifest or generated runtime configuration for an app."""
    return get_dev_manifest_action(app_id=app_id, workspace_id=workspace_id, db=db, guard=guard)

@router.put("/manifest")
def update_dev_manifest(
    app_id: str,
    body: AppManifestUpdateRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save or generate an app.yaml manifest directly into the app repository."""
    return update_dev_manifest_action(app_id=app_id, body=body, db=db, guard=guard)

