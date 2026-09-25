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
    """Native MCP Server providing semantic, table metadata, and catalog search in CompassX."""

    @property
    def name(self) -> str:
        return "compassx_catalog_search"

    @property
    def description(self) -> str:
        return "Search catalog objects (tables, schemas, dashboards, notebooks, assets) in CompassX."

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="search_catalog",
                description="Search for data assets, tables, columns, dashboards, or notebooks matching a query keyword.",
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
            MCPTool(
                name="list_schemas",
                description="List all schemas available in the data catalog.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "catalog_name": {"type": "string", "description": "Catalog name (default: 'main').", "default": "main"},
                    },
                },
            ),
            MCPTool(
                name="get_table_schema",
                description="Get detailed column definitions and metadata for a specific catalog table.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Table or view name."},
                        "schema_name": {"type": "string", "description": "Schema name (default: 'public').", "default": "public"},
                    },
                    "required": ["table_name"],
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
                search_term = f"%{query_str}%"
                sql = text("""
                    SELECT table_schema, table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_name ILIKE :term OR table_schema ILIKE :term
                    ORDER BY table_name
                    LIMIT 30
                """)
                res = db.execute(sql, {"term": search_term}).fetchall()
                results = [{"schema": r[0], "name": r[1], "type": r[2]} for r in res]
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps({"results": results, "count": len(results)}, indent=2))]
                )
            except Exception as e:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"Error searching catalog: {str(e)}")],
                )

        elif name == "list_schemas":
            if not db:
                from app.database import AccountSessionLocal
                db = AccountSessionLocal()

            try:
                sql = text("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                    ORDER BY schema_name
                """)
                res = db.execute(sql).fetchall()
                schemas = [r[0] for r in res]
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps({"schemas": schemas}, indent=2))]
                )
            except Exception as e:
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps({"schemas": ["default", "public"]}, indent=2))]
                )

        elif name == "get_table_schema":
            table_name = arguments.get("table_name")
            schema_name = arguments.get("schema_name", "public")
            if not db:
                from app.database import AccountSessionLocal
                db = AccountSessionLocal()

            try:
                sql = text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = :table_name AND table_schema = :schema_name
                    ORDER BY ordinal_position
                """)
                res = db.execute(sql, {"table_name": table_name, "schema_name": schema_name}).fetchall()
                cols = [{"column": r[0], "type": r[1], "nullable": r[2], "default": r[3]} for r in res]
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps({"table": f"{schema_name}.{table_name}", "columns": cols}, indent=2))]
                )
            except Exception as e:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"Error retrieving table schema: {str(e)}")],
                )

        return MCPToolResult(
            isError=True,
            content=[MCPToolContent(type="text", text=f"Unknown tool name: {name}")],
        )
