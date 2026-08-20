"""API routes for Agent Tool execution (POST /agent-tools/execute)."""

from __future__ import annotations

import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app.agents.services.agent.tools.external_tool_executor import execute_agent_tool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent Tools"])


class AgentToolExecuteRequest(BaseModel):
    tool_id: str = Field(..., description="Tool catalog ID or name")
    version: Optional[int] = Field(default=None, description="Pinned tool version per D11")
    connection_id: Optional[str] = Field(default=None, description="Explicit connection ID per D5")
    params: Optional[dict[str, Any]] = Field(default_factory=dict, description="Function parameters")
    session_id: Optional[str] = Field(default=None, description="Agent session ID")
    agent_type: Optional[str] = Field(default="nova", description="Calling agent type label")


class AgentToolExecuteResponse(BaseModel):
    ok: bool
    result: Optional[Any] = None
    truncated: bool = False
    error_type: Optional[str] = None
    message: Optional[str] = None
    retryable: Optional[bool] = None


@router.post(
    "/api/v1/agent-tools/execute",
    response_model=AgentToolExecuteResponse,
)
@router.post(
    "/agent-tools/execute",
    response_model=AgentToolExecuteResponse,
    include_in_schema=False,
)
async def execute_tool_endpoint(
    payload: AgentToolExecuteRequest,
    request: Request,
    current_user: Any = Depends(get_current_user),
):
    """Execute a promoted catalog tool in an isolated ephemeral execution pod."""
    user_id = getattr(current_user, "id", "default_user")
    if hasattr(user_id, "__str__"):
        user_id = str(user_id)

    res = await execute_agent_tool(
        tool_id=payload.tool_id,
        version=payload.version,
        connection_id=payload.connection_id,
        params=payload.params or {},
        session_id=payload.session_id,
        agent_type=payload.agent_type or "nova",
        invoked_by=user_id,
    )
    return AgentToolExecuteResponse(**res)
