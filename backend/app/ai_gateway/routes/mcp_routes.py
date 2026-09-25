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

router = APIRouter(prefix="/api/v1/ai-gateway/mcp", tags=["AI Gateway - MCP Services & Tools"])
logger = logging.getLogger(__name__)


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


@router.get("/config/omnigent")
def get_omnigent_mcp_config(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Return unified MCP server configurations formatted for Claude Code, OpenCode, Antigravity, and Codex harnesses."""
    ws_id = _get_workspace_id(request)
    return build_mcp_configs_from_gateway(db=db, workspace_id=ws_id)


@router.get("/sse")
async def mcp_sse_stream(
    request: Request,
):
    """
    Standard MCP SSE Stream endpoint for the unified CompassX platform.
    Clients connect via HTTP GET and receive the 'endpoint' event with the messages URI.
    """
    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)
    return await handle_mcp_sse_stream(
        request=request,
        server_filter=None,
        workspace_id=ws_id,
        user_email=user_email,
    )


@router.get("/servers/{server_name}/sse")
async def mcp_server_sse_stream(
    server_name: str,
    request: Request,
):
    """
    Standard MCP SSE Stream endpoint for a specific MCP server (built-in native or proxied).
    """
    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)
    return await handle_mcp_sse_stream(
        request=request,
        server_filter=server_name,
        workspace_id=ws_id,
        user_email=user_email,
    )


@router.post("/messages")
async def mcp_messages(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """
    Standard MCP JSON-RPC 2.0 message handler.
    Dispatches initialize, notifications/initialized, tools/list, tools/call, and ping requests.
    """
    session_id = request.query_params.get("session_id")
    session = mcp_session_manager.get_session(session_id) if session_id else None

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    ws_id = _get_workspace_id(request)
    user_email = getattr(request.state, "user_email", None)

    response = await process_mcp_jsonrpc_message(
        body=body,
        session=session,
        db=db,
        workspace_id=ws_id,
        user_email=user_email,
    )

    # If session has an active queue, also put message into queue
    if session and session.is_active and "result" in response:
        try:
            await session.queue.put(json.dumps(response))
        except Exception:
            pass

    return response


@router.get("/servers", response_model=list[MCPServerResponse])
def list_mcp_servers(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List registered MCP servers (both built-in native and remote/subprocess) in the current workspace."""
    ws_id = _get_workspace_id(request)
    base_url = _resolve_base_url(request)

    results: list[MCPServerResponse] = []
    # 1. Native Built-in servers
    for b_name, b_inst in BUILTIN_MCP_SERVERS.items():
        tool_list = [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema,
            }
            for t in b_inst.list_tools()
        ]
        results.append(
            MCPServerResponse(
                id=abs(hash(b_name)) % 100000 + 1,
                workspace_id=ws_id,
                catalog_name="system",
                schema_name="ai",
                full_name=f"system.ai.{b_name}",
                name=b_name,
                description=b_inst.description,
                server_type="native",
                endpoint_url=f"{base_url}/api/v1/ai-gateway/mcp/servers/{b_name}/sse",
                has_auth=False,
                command=None,
                is_enabled=True,
                created_by="system",
                cached_tools=tool_list,
                last_synced_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    # 2. Database registered servers
    query = db.query(MCPServer)
    if ws_id:
        query = query.filter((MCPServer.workspace_id == ws_id) | (MCPServer.workspace_id.is_(None)))
    servers = query.order_by(MCPServer.name).all()
    for s in servers:
        if not any(r.name == s.name for r in results):
            results.append(_to_mcp_response(s, base_url))

    return results


@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    body: MCPServerCreate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Register a new MCP server (Native, Remote SSE, or Subprocess) and auto-sync tools."""
    ws_id = _get_workspace_id(request)

    existing_query = db.query(MCPServer).filter(MCPServer.name == body.name)
    if ws_id:
        existing_query = existing_query.filter((MCPServer.workspace_id == ws_id) | (MCPServer.workspace_id.is_(None)))
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail=f"MCP server '{body.name}' already registered.")

    auth_enc = encrypt_field(json.dumps(body.auth_headers)) if body.auth_headers else None
    env_enc = encrypt_field(json.dumps(body.env_vars)) if body.env_vars else None
    s_type = body.server_type.value if hasattr(body.server_type, "value") else str(body.server_type)
    user_email = getattr(request.state, "user_email", None) or "system"

    server = MCPServer(
        workspace_id=ws_id,
        catalog_name=body.catalog_name,
        schema_name=body.schema_name,
        name=body.name,
        description=body.description,
        server_type=s_type,
        endpoint_url=body.endpoint_url,
        auth_config_enc=auth_enc,
        command=body.command,
        env_vars_enc=env_enc,
        is_enabled=body.is_enabled,
        created_by=user_email,
        cached_tools=[],
    )
    db.add(server)
    db.commit()
    db.refresh(server)

    # Immediately sync tools from remote server
    try:
        if server.server_type in ("remote_sse", "subprocess") and (server.endpoint_url or server.command):
            await MCPManager.sync_server_tools(db, server)
            db.refresh(server)
    except Exception as sync_err:
        logger.warning("Initial tools discovery for MCP server '%s' completed with warning: %s", server.name, sync_err)

    return _to_mcp_response(server)


@router.get("/servers/{server_id}", response_model=MCPServerResponse)
def get_mcp_server(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Get MCP server details by ID or catalog.schema.name."""
    ws_id = _get_workspace_id(request)
    server, _, _ = _resolve_mcp_server(server_id, db, ws_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return _to_mcp_response(server)


@router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Update MCP server configuration and refresh tools."""
    ws_id = _get_workspace_id(request)
    server, _, _ = _resolve_mcp_server(server_id, db, ws_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    if body.catalog_name is not None:
        server.catalog_name = body.catalog_name
    if body.schema_name is not None:
        server.schema_name = body.schema_name
    if body.name is not None:
        server.name = body.name
    if body.description is not None:
        server.description = body.description
    if body.server_type is not None:
        server.server_type = body.server_type.value if hasattr(body.server_type, "value") else str(body.server_type)
    if body.endpoint_url is not None:
        server.endpoint_url = body.endpoint_url
    if body.auth_headers is not None:
        server.auth_config_enc = encrypt_field(json.dumps(body.auth_headers)) if body.auth_headers else None
    if body.command is not None:
        server.command = body.command
    if body.env_vars is not None:
        server.env_vars_enc = encrypt_field(json.dumps(body.env_vars)) if body.env_vars else None
    if body.is_enabled is not None:
        server.is_enabled = body.is_enabled

    db.commit()
    db.refresh(server)

    # Sync tools if connection changed
    try:
        if server.server_type in ("remote_sse", "subprocess") and (server.endpoint_url or server.command):
            await MCPManager.sync_server_tools(db, server)
            db.refresh(server)
    except Exception as sync_err:
        logger.warning("Tools sync for updated MCP server '%s' warning: %s", server.name, sync_err)

    return _to_mcp_response(server)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Delete an MCP server registration."""
    ws_id = _get_workspace_id(request)
    server, _, _ = _resolve_mcp_server(server_id, db, ws_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    db.delete(server)
    db.commit()
    return None


@router.get("/servers/{server_id}/tools")
@router.post("/servers/{server_id}/tools")
@router.post("/servers/{server_id}/ping")
async def get_mcp_server_tools(
    server_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Retrieve the live tools list exposed by an MCP server (with real-time introspection and latency)."""
    import time

    start_time = time.perf_counter()
    ws_id = _get_workspace_id(request)
    db_server, builtin_name, builtin_inst = _resolve_mcp_server(server_id, db, ws_id)

    # Case 1: Built-in Native Servers
    if builtin_inst and builtin_name:
        tools = builtin_inst.list_tools()
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        tool_defs = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema,
            }
            for t in tools
        ]
        full_ref = f"system.ai.{builtin_name}"
        return {
            "success": True,
            "message": f"Successfully retrieved tools from native MCP server '{builtin_name}'",
            "latency_ms": latency_ms,
            "called_endpoint": f"/api/v1/ai-gateway/mcp/servers/{full_ref}/tools",
            "http_method": "GET",
            "mcp_method": "tools/list",
            "mcp_protocol": "JSON-RPC 2.0",
            "upstream_target": "compassx-internal-runtime",
            "server_id": builtin_name,
            "server_name": builtin_name,
            "server_full_name": full_ref,
            "server_type": "native",
            "endpoint_url": "compassx-internal-runtime",
            "tools_count": len(tool_defs),
            "tools": tool_defs,
            "raw_response": {
                "jsonrpc": "2.0",
                "result": {
                    "tools": tool_defs
                }
            }
        }

    # Case 2: Registered Database Servers (Remote SSE or Subprocess)
    if not db_server:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_id}' not found")

    server = db_server
    cat = server.catalog_name or "default"
    sch = server.schema_name or "default"
    full_ref = f"{cat}.{sch}.{server.name}"
    target = server.endpoint_url or server.command or "unknown"

    try:
        tools = await MCPManager.sync_server_tools(db, server)
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        tool_defs = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema,
            }
            for t in tools
        ]
        return {
            "success": True,
            "message": f"Successfully retrieved tools from MCP server '{server.name}' via {server.server_type.upper()}",
            "latency_ms": latency_ms,
            "called_endpoint": f"/api/v1/ai-gateway/mcp/servers/{full_ref}/tools",
            "http_method": "GET",
            "mcp_method": "tools/list",
            "mcp_protocol": "JSON-RPC 2.0",
            "upstream_target": target,
            "server_id": server.id,
            "server_name": server.name,
            "server_full_name": full_ref,
            "server_type": server.server_type,
            "endpoint_url": target,
            "tools_count": len(tool_defs),
            "tools": tool_defs,
            "raw_response": {
                "jsonrpc": "2.0",
                "result": {
                    "tools": tool_defs
                }
            }
        }
    except Exception as e:
        latency_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        logger.error("Error retrieving tools for MCP server %s: %s", server.name, e)
        return {
            "success": False,
            "message": f"Failed to retrieve tools: {str(e)}",
            "latency_ms": latency_ms,
            "called_endpoint": f"/api/v1/ai-gateway/mcp/servers/{full_ref}/tools",
            "http_method": "GET",
            "mcp_method": "tools/list",
            "mcp_protocol": "JSON-RPC 2.0",
            "upstream_target": target,
            "server_id": server.id,
            "server_name": server.name,
            "server_full_name": full_ref,
            "server_type": server.server_type,
            "endpoint_url": target,
            "tools_count": 0,
            "tools": [],
            "raw_response": {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
        }


@router.get("/tools", response_model=list[MCPToolDefinition])
async def list_tools(
    request: Request,
    db: Session = Depends(get_account_db),
):
    """List all aggregated tools available in the workspace (built-ins + external servers)."""
    ws_id = _get_workspace_id(request)
    return await MCPManager.list_all_tools_for_workspace(db, ws_id)


@router.post("/tools/call", response_model=MCPToolCallResponse)
async def call_tool(
    body: MCPToolCallRequest,
    request: Request,
    db: Session = Depends(get_account_db),
):
    """Execute an MCP tool call through the governed execution proxy."""
    ws_id = _get_workspace_id(request)
    return await MCPExecutionProxy.execute_tool(
        tool_name=body.tool_name,
        arguments=body.arguments,
        db=db,
        workspace_id=ws_id,
        user_id=None,
        caller_id=body.caller_id,
        server_id=body.server_id,
    )
