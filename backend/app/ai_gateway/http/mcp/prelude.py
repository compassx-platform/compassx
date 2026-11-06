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
