"""Built-in Native MCP Server: CompassX Catalog Search."""

from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins.base_builtin import BaseBuiltinMCPServer
from app.ai_gateway.mcp.types import MCPTool, MCPToolResult, MCPToolContent

logger = logging.getLogger(__name__)


class CatalogSearchMCPServer(BaseBuiltinMCPServer):
    """Native MCP Server providing semantic and metadata catalog search."""

    @property
    def name(self) -> str:
        return "compassx_catalog_search"

    @property
    def description(self) -> str:
        return "Search catalog objects (tables, schemas, dashboards, notebooks, tools) in CompassX."

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="search_catalog",
                description="Search for data assets, tables, columns, or documentation matching a search query keyword.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword or phrase."},
                        "asset_type": {
                            "type": "string",
                            "description": "Optional asset type filter: 'table', 'view', 'dashboard', 'notebook'.",
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        db: Session | None = None,
        workspace_id: str | None = None,
        user_id: str | None = None,
    ) -> MCPToolResult:
        if name == "search_catalog":
            query_str = arguments.get("query", "").strip()
            if not query_str:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text="Error: query parameter is required.")],
                )

            if not db:
                from app.database import AccountSessionLocal
                db = AccountSessionLocal()

            try:
                # Search tables in information_schema or catalog tables
                search_term = f"%{query_str}%"
                sql = text("""
                    SELECT table_schema, table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_name ILIKE :term OR table_schema ILIKE :term
                    LIMIT 20
                """)
                res = db.execute(sql, {"term": search_term}).fetchall()
                results = [{"schema": r[0], "name": r[1], "type": r[2]} for r in res]
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps({"results": results}, indent=2))]
                )
            except Exception as e:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"Error searching catalog: {str(e)}")],
                )

        return MCPToolResult(
            isError=True,
            content=[MCPToolContent(type="text", text=f"Unknown tool name: {name}")],
        )
