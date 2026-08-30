"""API routes for Agent Tool execution (POST /agent-tools/execute).

A catalog tool is arbitrary Python promoted out of a notebook and run in an
execution pod, so this endpoint is code execution addressed by name. It used to
take no privilege at all: any authenticated caller could name any tool in the
deployment, and any connection to run it against, because ``execute_agent_tool``
resolves both by id *or name* with no workspace filter of its own.

Two checks, one per securable the call touches:

* ``EXECUTE`` on the tool, which is a catalog-path securable and so inherits
  from its schema and catalog;
* ``USE_COMPUTE`` on the external connection, when one is named — the tool
  runs with that connection's decrypted credentials, so passing a
  ``connection_id`` is a request to act as it.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.models.external_connection import ExternalConnection
from app.agents.routes._authz import authorized_connection
from app.agents.services.agent.tools.external_tool_executor import execute_agent_tool
from app.catalog.models import UnifiedCatalogTool
from app.database import get_account_db, get_system_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable

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


def _authorized_tool(db: Session, guard: Guard, tool_id: str) -> UnifiedCatalogTool:
    """Resolve a tool by id or name and require EXECUTE on it.

    The same id-or-name resolution the executor does, performed here so the
    privilege is checked against the tool that will actually run rather than
    against whatever the caller claimed.
    """
    tool = (
        db.query(UnifiedCatalogTool)
        .filter(UnifiedCatalogTool.id == tool_id)
        .first()
    ) or (
        db.query(UnifiedCatalogTool)
        .filter(UnifiedCatalogTool.name == tool_id)
        .first()
    )
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found in catalog.")
    guard.require(
        Privilege.EXECUTE,
        Securable.tool(tool.catalog_name, tool.schema_name, tool.name),
    )
    return tool


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
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Execute a promoted catalog tool in an isolated ephemeral execution pod."""
    tool = _authorized_tool(account_db, guard, payload.tool_id)
    if payload.connection_id:
        authorized_connection(
            system_db, guard, ExternalConnection, payload.connection_id, Privilege.USE_COMPUTE
        )

    res = await execute_agent_tool(
        # The resolved id, not the caller's string: the executor would
        # otherwise redo the name lookup and could land on a different row.
        tool_id=tool.id,
        version=payload.version,
        connection_id=payload.connection_id,
        params=payload.params or {},
        session_id=payload.session_id,
        agent_type=payload.agent_type or "nova",
        invoked_by=str(guard.principal.id),
    )
    return AgentToolExecuteResponse(**res)
