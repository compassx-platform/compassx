"""Built-in Native MCP Server: CompassX SQL Warehouse."""

from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins.base_builtin import BaseBuiltinMCPServer
from app.ai_gateway.mcp.types import MCPTool, MCPToolResult, MCPToolContent

logger = logging.getLogger(__name__)


class SQLWarehouseMCPServer(BaseBuiltinMCPServer):
    """Native MCP Server providing SQL execution and schema introspection."""

    @property
    def name(self) -> str:
        return "compassx_sql_warehouse"

    @property
    def description(self) -> str:
        return "Execute SQL queries and inspect schema catalogs in CompassX."

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="execute_sql",
                description="Execute a SELECT SQL query against the CompassX data warehouse and return rows (up to 100).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The SQL query to execute."},
                        "max_rows": {"type": "integer", "description": "Maximum number of rows to return (default: 50, max: 100)."},
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="list_tables",
                description="List accessible tables and views in the current catalog schema.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "schema_name": {"type": "string", "description": "Schema name to filter (default: 'public')."},
                    },
                },
            ),
            MCPTool(
                name="describe_table",
                description="Describe column names, types, and constraints of a specific table.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Name of the table to describe."},
                        "schema_name": {"type": "string", "description": "Schema name (default: 'public')."},
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
        if name == "execute_sql":
            query = arguments.get("query", "").strip()
            max_rows = min(int(arguments.get("max_rows", 50)), 100)

            # Safety check: Prevent destructive statements through default tool
            lower_q = query.lower()
            if any(lower_q.startswith(kw) for kw in ["drop ", "truncate ", "delete from ", "alter "]):
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text="Error: Destructive DDL/DML statements are not allowed via this tool.")],
                )

            if not db:
                from app.database import AccountSessionLocal
                db = AccountSessionLocal()

            try:
                result = db.execute(text(query))
                if result.returns_rows:
                    columns = list(result.keys())
                    rows = [dict(zip(columns, row)) for row in result.fetchmany(max_rows)]
                    # Serialize to JSON safe
                    output = {"columns": columns, "row_count": len(rows), "rows": rows}
                    return MCPToolResult(
                        content=[MCPToolContent(type="text", text=json.dumps(output, default=str, indent=2))]
                    )
                else:
                    return MCPToolResult(
                        content=[MCPToolContent(type="text", text=f"Query executed successfully. Rows affected: {result.rowcount}")]
                    )
            except Exception as e:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"SQL Execution Error: {str(e)}")],
                )

        elif name == "list_tables":
            schema_name = arguments.get("schema_name", "public")
            if not db:
                from app.database import AccountSessionLocal
                db = AccountSessionLocal()

            try:
                query = text("""
                    SELECT table_schema, table_name, table_type 
                    FROM information_schema.tables 
                    WHERE table_schema = :schema_name
                    ORDER BY table_name
                """)
                res = db.execute(query, {"schema_name": schema_name}).fetchall()
                tables = [{"schema": r[0], "name": r[1], "type": r[2]} for r in res]
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps(tables, indent=2))]
                )
            except Exception as e:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"Error listing tables: {str(e)}")],
                )

        elif name == "describe_table":
            table_name = arguments.get("table_name")
            schema_name = arguments.get("schema_name", "public")
            if not db:
                from app.database import AccountSessionLocal
                db = AccountSessionLocal()

            try:
                query = text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = :table_name AND table_schema = :schema_name
                    ORDER BY ordinal_position
                """)
                res = db.execute(query, {"table_name": table_name, "schema_name": schema_name}).fetchall()
                cols = [{"column": r[0], "type": r[1], "nullable": r[2], "default": r[3]} for r in res]
                return MCPToolResult(
                    content=[MCPToolContent(type="text", text=json.dumps(cols, indent=2))]
                )
            except Exception as e:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"Error describing table: {str(e)}")],
                )

        return MCPToolResult(
            isError=True,
            content=[MCPToolContent(type="text", text=f"Unknown tool name: {name}")],
        )
