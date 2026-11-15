"""Host adapter for Nova platform tools invoked from an isolated sandbox."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request

from app.agent_runtime.service import agent_runtime_service
from sandbox_nova.tools.platform import PLATFORM_TOOL_NAMES

logger = logging.getLogger(__name__)

LOCAL_ONLY = {"python_code", "run_shell", "list_files", "read_file", "write_file"}


def file_task_from_session(session, arguments: dict[str, Any], service=None) -> dict[str, Any]:
    """File a draft task linked to the session the person is already in."""
    from app.agent_runtime.models import CreateAgentTaskRequest
    from app.agent_runtime import tasks as agent_tasks

    title = str((arguments or {}).get("title") or "").strip()
    brief = str((arguments or {}).get("brief") or (arguments or {}).get("description") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="A task title is required.")
    task = agent_tasks.create_task(
        service or agent_runtime_service,
        CreateAgentTaskRequest(
            title=title,
            brief=brief,
            project_id=session.project_id,
            source_session_id=session.id,
            agent_type=session.agent_type or "nova",
            llm_model=session.llm_model,
            actor="agent",
        ),
        workspace_id=session.workspace_id,
    )
    return {
        "task_id": task.id,
        "title": task.title,
        "stage": task.stage,
        "source_session_id": task.source_session_id,
        "message": "Filed as a draft. It stays in Tasks until a person marks it ready.",
    }


def resolve_sandbox_workspace(request: Request) -> str:
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sandbox token required.")
    token = auth[7:].strip()
    if token.startswith("cx_gw_ws_"):
        from app.services.sandbox_credentials import workspace_id_for_gateway_token

        workspace_id = workspace_id_for_gateway_token(token)
        if not workspace_id:
            raise HTTPException(status_code=401, detail="Invalid gateway token.")
        return workspace_id
    header = (request.headers.get("X-Workspace-Id") or "").strip()
    if header:
        return header
    raise HTTPException(status_code=401, detail="Invalid sandbox identity.")


async def execute_platform_tool(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    name = str(body.get("name") or "").strip()
    if name in LOCAL_ONLY or name not in PLATFORM_TOOL_NAMES:
        raise HTTPException(status_code=403, detail=f"Tool '{name}' cannot run on the host.")
    workspace_id = resolve_sandbox_workspace(request)
    session_id = str(body.get("session_id") or request.headers.get("X-CompassX-Runtime-Session") or "").strip()
    session = agent_runtime_service.get_session(session_id) if session_id else None
    if not session:
        raise HTTPException(status_code=404, detail="Runtime session not found for this sandbox.")
    if session.workspace_id and session.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Sandbox token does not match this session.")
    from app.agent_runtime.nova import ensure_nova_agent
    from app.agents.services.agent.tool_executor import execute_tool
    from app.database import SystemSessionLocal

    if SystemSessionLocal is None:
        raise HTTPException(status_code=503, detail="System database is unavailable.")
    arguments = body.get("arguments") if isinstance(body.get("arguments"), dict) else {}
    if name == "file_task":
        return file_task_from_session(session, arguments)
    db = SystemSessionLocal()
    try:
        agent = ensure_nova_agent(db, session.workspace_id)
        result = await execute_tool(
            name,
            arguments,
            agent,
            db,
            runtime_context={"sandbox_id": session.sandbox_id, "runtime_session_id": session.id},
        )
        return result
    finally:
        db.close()
