"""FastAPI routes for the Sandbox Module."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.sandbox.models import ExecResult, SandboxInstance, SandboxSpec, SandboxStatus
from app.sandbox.service import sandbox_service

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
    ctx = getattr(request.state, "workspace", None)
    ws_id = str(ctx.workspace_id) if ctx else None
    return sandbox_service.list_sandboxes(
        workspace_id=ws_id,
        consumer_module=consumer_module,
        status=status,
    )


@router.post("", response_model=SandboxInstance, status_code=201)
def provision_sandbox(
    request: Request,
    spec: SandboxSpec,
):
    """Provision a new compute sandbox."""
    ctx = getattr(request.state, "workspace", None)
    if not spec.workspace_id and ctx:
        spec.workspace_id = str(ctx.workspace_id)
    handle = sandbox_service.provision_sandbox(spec)
    return handle.instance


@router.post("/ensure", response_model=SandboxInstance)
def ensure_sandbox(
    request: Request,
    spec: SandboxSpec,
):
    """Idempotently ensure a sandbox is active. Returns existing instance if already running, or provisions with stage tracking."""
    ctx = getattr(request.state, "workspace", None)
    if not spec.workspace_id and ctx:
        spec.workspace_id = str(ctx.workspace_id)
    return sandbox_service.ensure_sandbox(spec)



@router.get("/{sandbox_id}", response_model=SandboxInstance)
def get_sandbox(sandbox_id: str):
    """Get status and endpoints of a specific sandbox."""
    instance = sandbox_service.get_sandbox(sandbox_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found")
    return instance


@router.delete("/{sandbox_id}")
def delete_sandbox(sandbox_id: str):
    """Terminate and destroy a sandbox."""
    ok = sandbox_service.terminate_sandbox(sandbox_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be terminated")
    return {"terminated": True, "sandbox_id": sandbox_id}


@router.post("/{sandbox_id}/terminate")
def terminate_sandbox(sandbox_id: str):
    """Terminate and destroy a sandbox."""
    ok = sandbox_service.terminate_sandbox(sandbox_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be terminated")
    return {"terminated": True, "sandbox_id": sandbox_id}


@router.post("/{sandbox_id}/suspend")
def suspend_sandbox(sandbox_id: str):
    """Suspend compute resources of a sandbox."""
    ok = sandbox_service.suspend_sandbox(sandbox_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be suspended")
    return {"suspended": True, "sandbox_id": sandbox_id}


@router.post("/{sandbox_id}/resume")
def resume_sandbox(sandbox_id: str):
    """Resume compute resources of a sandbox."""
    ok = sandbox_service.resume_sandbox(sandbox_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Sandbox '{sandbox_id}' not found or could not be resumed")
    return {"resumed": True, "sandbox_id": sandbox_id}


@router.get("/{sandbox_id}/logs")
def get_sandbox_logs(sandbox_id: str, max_lines: int = Query(default=200, ge=1, le=2000)):
    """Fetch recent execution logs for a sandbox."""
    logs = sandbox_service.get_sandbox_logs(sandbox_id, max_lines=max_lines)
    return {"sandbox_id": sandbox_id, "logs": logs}


@router.post("/{sandbox_id}/exec", response_model=ExecResult)
def exec_in_sandbox(sandbox_id: str, body: ExecRequestBody):
    """Run a shell command inside a sandbox container/workspace."""
    return sandbox_service.exec_in_sandbox(
        sandbox_id=sandbox_id,
        command=body.command,
        working_dir=body.working_dir,
        env=body.env,
        timeout=body.timeout,
    )
