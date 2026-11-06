"""AI Gateway Model Context Protocol (MCP) Server and Tool Routes."""

from __future__ import annotations

import json

import logging

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins import BUILTIN_MCP_SERVERS

from app.ai_gateway.mcp.manager import MCPManager

from app.ai_gateway.mcp.omnigent_sync import build_mcp_configs_from_gateway

from app.ai_gateway.mcp.proxy import MCPExecutionProxy

from app.ai_gateway.mcp.sse_server import (
    handle_mcp_sse_stream,
    mcp_session_manager,
    process_mcp_jsonrpc_message,
)

from app.ai_gateway.models.mcp import MCPServer

from app.ai_gateway.schemas.mcp import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerSyncResponse,
    MCPServerUpdate,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolDefinition,
)

from app.database import get_account_db

from app.services.encryption import encrypt_field

logger = logging.getLogger("app.ai_gateway.routes.mcp_routes")
def _get_workspace_id(request: Request) -> str | None:
    ctx = getattr(request.state, "workspace", None)
    if ctx and hasattr(ctx, "workspace_id"):
        try:
            import uuid
            uuid.UUID(str(ctx.workspace_id))
            return str(ctx.workspace_id)
        except Exception:
            return None
    ws_header = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id")
    if ws_header:
        try:
            import uuid
            uuid.UUID(str(ws_header))
            return str(ws_header)
        except Exception:
            return None
    return None

def _resolve_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "135.13.180.167.nip.io"
    return f"{proto}://{host}".rstrip("/")

def _to_mcp_response(server: MCPServer, base_url: str = "") -> MCPServerResponse:
    cat = server.catalog_name or "default"
    sch = server.schema_name or "default"
    endpoint = server.endpoint_url
    if not endpoint and server.server_type == "native" and base_url:
        endpoint = f"{base_url}/api/v1/ai-gateway/mcp/servers/{server.name}/sse"
    return MCPServerResponse(
        id=server.id,
        workspace_id=str(server.workspace_id) if server.workspace_id else None,
        catalog_name=server.catalog_name,
        schema_name=server.schema_name,
        full_name=f"{cat}.{sch}.{server.name}",
        name=server.name,
        description=server.description,
        server_type=server.server_type,
        endpoint_url=endpoint,
        has_auth=bool(server.auth_config_enc),
        command=server.command,
        is_enabled=server.is_enabled,
        created_by=server.created_by,
        cached_tools=server.cached_tools or [],
        last_synced_at=server.last_synced_at,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )

def _resolve_mcp_server(
    identifier: str,
    db: Session,
    workspace_id: str | None = None,
) -> tuple[MCPServer | None, str | None, Any | None]:
    """
    Resolve an MCP server from any supported identifier format:
    1. 3-tier catalog reference: 'catalog.schema.server_name' (e.g. 'system.ai.postgres_mcp')
    2. 2-tier schema reference: 'schema.server_name' (e.g. 'ai.postgres_mcp')
    3. Direct server name: 'postgres_mcp'
    4. Native built-in aliases: 'compassx_sql_warehouse', 'native_sql', 'system.ai.compassx_sql_warehouse', etc.
    5. Numeric ID (legacy): '1'
    
    Returns: (db_server, builtin_canonical_name, builtin_instance)
    """
    import app.workspace.models  # Ensure workspace tables are registered in SQLAlchemy metadata
    from app.ai_gateway.mcp.builtins import BUILTIN_MCP_SERVERS

    # Check built-in aliases first
    builtin_aliases = {
        "native_sql": "compassx_sql_warehouse",
        "native_catalog": "compassx_catalog_search",
        "system.ai.compassx_sql_warehouse": "compassx_sql_warehouse",
        "system.ai.compassx_catalog_search": "compassx_catalog_search",
        "system.ai.native_sql": "compassx_sql_warehouse",
        "system.ai.native_catalog": "compassx_catalog_search",
    }
    canonical_builtin = builtin_aliases.get(identifier.lower(), identifier)
    if canonical_builtin in BUILTIN_MCP_SERVERS:
        return None, canonical_builtin, BUILTIN_MCP_SERVERS[canonical_builtin]

    for b_k, b_v in BUILTIN_MCP_SERVERS.items():
        if b_k.lower() == canonical_builtin.lower():
            return None, b_k, b_v

    query = db.query(MCPServer)
    if workspace_id:
        query = query.filter((MCPServer.workspace_id == workspace_id) | (MCPServer.workspace_id.is_(None)))

    # 1. Check 3-tier or 2-tier catalog.schema.name
    if "." in identifier:
        parts = identifier.split(".")
        if len(parts) == 3:
            cat, sch, s_name = parts[0], parts[1], parts[2]
            server = query.filter(
                (MCPServer.catalog_name == cat) | ((MCPServer.catalog_name.is_(None)) & (cat == "default")),
                (MCPServer.schema_name == sch) | ((MCPServer.schema_name.is_(None)) & (sch == "default")),
                MCPServer.name == s_name,
            ).first()
            if server:
                return server, None, None
            # Fallback by name
            server = query.filter(MCPServer.name == s_name).first()
            if server:
                return server, None, None
        elif len(parts) == 2:
            sch, s_name = parts[0], parts[1]
            server = query.filter(
                (MCPServer.schema_name == sch) | ((MCPServer.schema_name.is_(None)) & (sch == "default")),
                MCPServer.name == s_name,
            ).first()
            if server:
                return server, None, None

    # 2. Check Numeric ID
    if identifier.isdigit():
        server = query.filter(MCPServer.id == int(identifier)).first()
        if server:
            return server, None, None

    # 3. Check simple name
    server = query.filter(MCPServer.name == identifier).first()
    if server:
        return server, None, None

    return None, None, None

import app.ai_gateway.http.mcp.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.ai_gateway.http.mcp.application.get_omnigent_mcp_config import get_omnigent_mcp_config as get_omnigent_mcp_config_action
from app.ai_gateway.http.mcp.application.mcp_sse_stream import mcp_sse_stream as mcp_sse_stream_action
from app.ai_gateway.http.mcp.application.mcp_server_sse_stream import mcp_server_sse_stream as mcp_server_sse_stream_action
from app.ai_gateway.http.mcp.application.mcp_server_streamable_post import mcp_server_streamable_post as mcp_server_streamable_post_action
from app.ai_gateway.http.mcp.application.mcp_root_streamable_post import mcp_root_streamable_post as mcp_root_streamable_post_action
from app.ai_gateway.http.mcp.application.mcp_messages import mcp_messages as mcp_messages_action
from app.ai_gateway.http.mcp.application.list_mcp_servers import list_mcp_servers as list_mcp_servers_action
from app.ai_gateway.http.mcp.application.create_mcp_server import create_mcp_server as create_mcp_server_action
from app.ai_gateway.http.mcp.application.get_mcp_server import get_mcp_server as get_mcp_server_action
from app.ai_gateway.http.mcp.application.update_mcp_server import update_mcp_server as update_mcp_server_action
from app.ai_gateway.http.mcp.application.delete_mcp_server import delete_mcp_server as delete_mcp_server_action
from app.ai_gateway.http.mcp.application.get_mcp_server_tools import get_mcp_server_tools as get_mcp_server_tools_action
from app.ai_gateway.http.mcp.application.list_tools import list_tools as list_tools_action
from app.ai_gateway.http.mcp.application.call_tool import call_tool as call_tool_action

logger = logging.getLogger("app.ai_gateway.routes.mcp_routes")

router = APIRouter(prefix="/api/v1/ai-gateway/mcp", tags=["AI Gateway - MCP Services & Tools"])

@router.get("/config/omnigent")
def get_omnigent_mcp_config(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Return unified MCP server configurations formatted for Claude Code, OpenCode, Antigravity, and Codex harnesses."""
    return get_omnigent_mcp_config_action(request=request, db=db)

@router.get("/sse")
async def mcp_sse_stream(
    request: Request,
):
    """
    Standard MCP SSE Stream endpoint for the unified CompassX platform.
    Clients connect via HTTP GET and receive the 'endpoint' event with the messages URI.
    """
    return await mcp_sse_stream_action(request=request)

@router.get("/servers/{server_name}/mcp")
@router.get("/servers/{server_name}/sse")
async def mcp_server_sse_stream(
    server_name: str,
    request: Request,
):
    """
    Standard MCP SSE Stream endpoint for a specific MCP server (built-in native or proxied).
    """
    return await mcp_server_sse_stream_action(server_name=server_name, request=request)

@router.post("/servers/{server_name}/sse")
@router.post("/servers/{server_name}/mcp")
@router.post("/servers/{server_name}")
async def mcp_server_streamable_post(
    server_name: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """
    Streamable HTTP MCP endpoint (spec 2025-03-26) for a specific MCP server.
    Handles direct JSON-RPC 2.0 requests from Antigravity CLI, Claude Code, and modern MCP clients.
    """
    return await mcp_server_streamable_post_action(server_name=server_name, request=request, db=db)

@router.post("/sse")
@router.post("/mcp")
async def mcp_root_streamable_post(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """
    Streamable HTTP MCP root endpoint (spec 2025-03-26) for unified platform MCP tools.
    """
    return await mcp_root_streamable_post_action(request=request, db=db)

@router.post("/messages")
async def mcp_messages(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """
    Standard MCP JSON-RPC 2.0 message handler.
    Dispatches initialize, notifications/initialized, tools/list, tools/call, and ping requests.
    """
    return await mcp_messages_action(request=request, db=db)

@router.get("/servers", response_model=list[MCPServerResponse])
def list_mcp_servers(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List registered MCP servers (both built-in native and remote/subprocess) in the current workspace."""
    return list_mcp_servers_action(request=request, db=db)

@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    body: MCPServerCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Register a new MCP server (Native, Remote SSE, or Subprocess) and auto-sync tools."""
    return await create_mcp_server_action(body=body, request=request, db=db)

@router.get("/servers/{server_id}", response_model=MCPServerResponse)
def get_mcp_server(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get MCP server details by ID or catalog.schema.name."""
    return get_mcp_server_action(server_id=server_id, request=request, db=db)

@router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update MCP server configuration and refresh tools."""
    return await update_mcp_server_action(server_id=server_id, body=body, request=request, db=db)

@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an MCP server registration."""
    return delete_mcp_server_action(server_id=server_id, request=request, db=db)

@router.get("/servers/{server_id}/tools")
@router.post("/servers/{server_id}/tools")
@router.post("/servers/{server_id}/ping")
async def get_mcp_server_tools(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Retrieve the live tools list exposed by an MCP server (with real-time introspection and latency)."""
    return await get_mcp_server_tools_action(server_id=server_id, request=request, db=db)

@router.get("/tools", response_model=list[MCPToolDefinition])
async def list_tools(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all aggregated tools available in the workspace (built-ins + external servers)."""
    return await list_tools_action(request=request, db=db)

@router.post("/tools/call", response_model=MCPToolCallResponse)
async def call_tool(
    body: MCPToolCallRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Execute an MCP tool call through the governed execution proxy."""
    return await call_tool_action(body=body, request=request, db=db)
