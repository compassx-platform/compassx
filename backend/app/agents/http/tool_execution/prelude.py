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

logger = logging.getLogger("app.agents.routes.agent_tool_routes")

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
