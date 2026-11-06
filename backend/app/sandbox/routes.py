"""FastAPI routes for the Sandbox Module.

Handlers stay here. Each one forwards to one application type.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, Request, WebSocket
from pydantic import BaseModel, Field

from app.sandbox.http.application.delete_sandbox import delete_sandbox as delete_sandbox_action
from app.sandbox.http.application.ensure_sandbox import ensure_sandbox as ensure_sandbox_action
from app.sandbox.http.application.exec_in_sandbox import exec_in_sandbox as exec_in_sandbox_action
from app.sandbox.http.application.get_sandbox import get_sandbox as get_sandbox_action
from app.sandbox.http.application.get_sandbox_logs import get_sandbox_logs as get_sandbox_logs_action
from app.sandbox.http.application.list_sandboxes import list_sandboxes as list_sandboxes_action
from app.sandbox.http.application.provision_sandbox import provision_sandbox as provision_sandbox_action
from app.sandbox.http.application.resume_sandbox import resume_sandbox as resume_sandbox_action
from app.sandbox.http.application.sandbox_terminal_websocket import (
    sandbox_terminal_websocket as sandbox_terminal_websocket_action,
)
from app.sandbox.http.application.suspend_sandbox import suspend_sandbox as suspend_sandbox_action
from app.sandbox.http.application.terminate_sandbox import terminate_sandbox as terminate_sandbox_action
from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec

router = APIRouter(prefix="/sandboxes", tags=["sandbox"])


class ExecRequestBody(BaseModel):
    command: Any = Field(description="Shell command string or list of argument tokens")
    working_dir: Optional[str] = Field(default=None, description="Working directory inside sandbox")
    env: Optional[Dict[str, str]] = Field(default=None, description="Custom environment variables")
    timeout: int = Field(default=60, description="Command timeout in seconds")


@router.get("", response_model=List[SandboxInstance])
def list_sandboxes(
    request: Request,
    consumer_module: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    """List all active and discovered sandboxes."""
    return list_sandboxes_action(request, consumer_module, status)


@router.post("", response_model=SandboxInstance, status_code=201)
def provision_sandbox(
    request: Request,
    spec: SandboxSpec,
):
    """Provision a new compute sandbox."""
    return provision_sandbox_action(request, spec)


@router.post("/ensure", response_model=SandboxInstance)
def ensure_sandbox(
    request: Request,
    spec: SandboxSpec,
):
    """Idempotently ensure a sandbox is active. Returns existing instance if already running, or provisions with stage tracking."""
    return ensure_sandbox_action(request, spec)


@router.get("/{sandbox_id}", response_model=SandboxInstance)
def get_sandbox(sandbox_id: str):
    """Get status and endpoints of a specific sandbox."""
    return get_sandbox_action(sandbox_id)


@router.delete("/{sandbox_id}")
def delete_sandbox(sandbox_id: str):
    """Terminate and destroy a sandbox."""
    return delete_sandbox_action(sandbox_id)


@router.post("/{sandbox_id}/terminate")
def terminate_sandbox(sandbox_id: str):
    """Terminate and destroy a sandbox."""
    return terminate_sandbox_action(sandbox_id)


@router.post("/{sandbox_id}/suspend")
def suspend_sandbox(sandbox_id: str):
    """Suspend compute resources of a sandbox."""
    return suspend_sandbox_action(sandbox_id)


@router.post("/{sandbox_id}/resume")
def resume_sandbox(sandbox_id: str):
    """Resume compute resources of a sandbox."""
    return resume_sandbox_action(sandbox_id)


@router.get("/{sandbox_id}/logs")
def get_sandbox_logs(sandbox_id: str, max_lines: int = Query(default=200, ge=1, le=2000)):
    """Fetch recent execution logs for a sandbox."""
    return get_sandbox_logs_action(sandbox_id, max_lines)


@router.post("/{sandbox_id}/exec", response_model=ExecResult)
def exec_in_sandbox(sandbox_id: str, body: ExecRequestBody):
    """Run a shell command inside a sandbox container/workspace."""
    return exec_in_sandbox_action(sandbox_id, body)


@router.websocket("/{sandbox_id}/terminal/ws")
async def sandbox_terminal_websocket(
    websocket: WebSocket,
    sandbox_id: str,
    cols: int = Query(100),
    rows: int = Query(30),
    working_dir: Optional[str] = Query(None),
    command: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
):
    """Interactive real-time WebSocket PTY terminal for any compute sandbox."""
    await sandbox_terminal_websocket_action(
        websocket, sandbox_id, cols, rows, working_dir, command, agent, session_id
    )
