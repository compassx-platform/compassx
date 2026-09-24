"""MCP Server Manager and Tool Aggregator."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins import BUILTIN_MCP_SERVERS
from app.ai_gateway.mcp.client import MCPClient
from app.ai_gateway.mcp.types import MCPTool
from app.ai_gateway.models.mcp import MCPServer, MCPServerType
from app.ai_gateway.schemas.chat import ToolDefinition, ToolDefinitionFunction
from app.ai_gateway.schemas.mcp import MCPToolDefinition
from app.services.encryption import decrypt_field, encrypt_field

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages MCP server registrations, tool discovery, and tool schema aggregation."""

    @staticmethod
    def get_builtin_tools() -> list[MCPToolDefinition]:
        """Return tool definitions from all registered native built-in servers."""
        tools = []
        for s_name, s_inst in BUILTIN_MCP_SERVERS.items():
            for t in s_inst.list_tools():
                schema = t.inputSchema.model_dump() if hasattr(t.inputSchema, "model_dump") else t.inputSchema
                tools.append(MCPToolDefinition(
                    name=t.name,
                    description=t.description,
                    input_schema=schema or {},
                    server_name=s_name,
                ))
        return tools

    @staticmethod
    async def list_all_tools_for_workspace(
        db: Session,
        workspace_id: str | None = None,
    ) -> list[MCPToolDefinition]:
        """Aggregate all available tools (built-ins + enabled workspace MCP servers)."""
        tools = MCPManager.get_builtin_tools()

        # Query database for external/subprocess servers
        query = db.query(MCPServer).filter(MCPServer.is_enabled == True)  # noqa: E712
        if workspace_id:
            query = query.filter((MCPServer.workspace_id == workspace_id) | (MCPServer.workspace_id.is_(None)))
        servers = query.all()

        for s in servers:
            cached = s.cached_tools or []
            for t in cached:
                tools.append(MCPToolDefinition(
                    name=t.get("name", ""),
                    description=t.get("description"),
                    input_schema=t.get("inputSchema") or t.get("input_schema") or {},
                    server_id=s.id,
                    server_name=s.name,
                ))
        return tools

    @staticmethod
    async def get_openai_tool_definitions(
        db: Session,
        workspace_id: str | None = None,
        filter_tools: list[str] | None = None,
    ) -> list[ToolDefinition]:
        """Return active tools converted to OpenAI-compatible ToolDefinition objects."""
        all_tools = await MCPManager.list_all_tools_for_workspace(db, workspace_id)
        openai_tools: list[ToolDefinition] = []

        for t in all_tools:
            if filter_tools and t.name not in filter_tools:
                continue
            openai_tools.append(ToolDefinition(
                type="function",
                function=ToolDefinitionFunction(
                    name=t.name,
                    description=t.description or "",
                    parameters=t.input_schema if t.input_schema else {"type": "object", "properties": {}},
                ),
            ))
        return openai_tools

    @staticmethod
    async def sync_server_tools(db: Session, server: MCPServer) -> list[MCPTool]:
        """Fetch live tool list from an external MCP server and update database cache."""
        if server.server_type == MCPServerType.native:
            builtin = BUILTIN_MCP_SERVERS.get(server.name)
            tools = builtin.list_tools() if builtin else []
        else:
            auth_headers = {}
            if server.auth_config_enc:
                try:
                    dec = decrypt_field(server.auth_config_enc)
                    auth_headers = json.loads(dec) if dec else {}
                except Exception as e:
                    logger.warning("Could not decrypt auth config for MCP server %s: %s", server.name, e)

            env_vars = {}
            if server.env_vars_enc:
                try:
                    dec = decrypt_field(server.env_vars_enc)
                    env_vars = json.loads(dec) if dec else {}
                except Exception as e:
                    logger.warning("Could not decrypt env vars for MCP server %s: %s", server.name, e)

            client = MCPClient(
                endpoint_url=server.endpoint_url,
                auth_headers=auth_headers,
                command=server.command,
                env_vars=env_vars,
            )
            tools = await client.list_tools()

        # Update cache
        server.cached_tools = [t.model_dump() for t in tools]
        server.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(server)
        return tools
