"""Host adapter for Nova platform tools invoked from an isolated sandbox."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request

from app.agent_runtime.service import agent_runtime_service
from sandbox_nova.tools.platform import PLATFORM_TOOL_NAMES

logger = logging.getLogger(__name__)

LOCAL_ONLY = {"python_code", "run_shell", "list_files", "read_file", "write_file"}


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
