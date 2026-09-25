"""Built-in Native MCP Server: CompassX Notebook Manager."""

from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins.base_builtin import BaseBuiltinMCPServer
from app.ai_gateway.mcp.types import MCPTool, MCPToolResult, MCPToolContent
from app.agents.services.agent.tools.platform.notebooks.operations import (
    NOTEBOOK_MANAGER_OPERATIONS,
    execute_notebook_manager_operation,
)

logger = logging.getLogger(__name__)


class NotebookManagerMCPServer(BaseBuiltinMCPServer):
    """Native MCP Server for managing, editing, and executing CompassX Notebooks."""

    @property
    def name(self) -> str:
        return "compassx_notebook_manager"

    @property
    def description(self) -> str:
        return "Inspect, edit, execute cells, and author CompassX Notebooks."

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="notebook_manage",
                description=(
                    "Execute notebook operations. Operations include: "
                    "'create_notebook', 'read_notebook', 'run_cell', 'edit_cell', "
                    "'add_multiple_cells', 'get_cell_output', 'get_variable_state', "
                    "'list_imports', 'get_schema'. "
                    "When generating data to persist into the Catalog, use cx.write_table(df, 'catalog.schema.table', mode='overwrite')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": NOTEBOOK_MANAGER_OPERATIONS,
                            "description": "The notebook operation to perform.",
                        },
                        "payload": {
                            "type": "object",
                            "description": "Operation payload (e.g. {catalog_name, schema_name, notebook_name, code} or {cell_index, code}).",
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional runtime context (e.g. notebook_id, workspace_id).",
                        },
                    },
                    "required": ["operation", "payload"],
                },
            ),
            MCPTool(
                name="create_notebook",
                description="Create a new notebook in the specified catalog and schema.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "catalog_name": {"type": "string", "description": "Catalog name (e.g. 'main')."},
                        "schema_name": {"type": "string", "description": "Schema name (e.g. 'default')."},
                        "notebook_name": {"type": "string", "description": "Name for the new notebook."},
                        "code": {"type": "string", "description": "Initial Python or SQL code for the first cell."},
                        "comment": {"type": "string", "description": "Optional notebook description."},
                    },
                    "required": ["catalog_name", "schema_name", "notebook_name"],
                },
            ),
            MCPTool(
                name="read_notebook",
                description="Read the cells and contents of a notebook by path or ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_path": {"type": "string", "description": "Path or identifier of the notebook."},
                        "include_outputs": {"type": "boolean", "description": "Whether to include cell outputs.", "default": True},
                    },
                    "required": ["notebook_path"],
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
        try:
            if name == "notebook_manage":
                op = str(arguments.get("operation") or "")
                payload = arguments.get("payload") or {}
                context = arguments.get("context") or {}
                if workspace_id and "workspace_id" not in context:
                    context["workspace_id"] = workspace_id

                res = execute_notebook_manager_operation(op, payload, context)
                return MCPToolResult(
                    isError=not res.get("ok", False),
                    content=[MCPToolContent(type="text", text=json.dumps(res, indent=2, default=str))],
                )

            elif name == "create_notebook":
                payload = {
                    "catalog_name": arguments.get("catalog_name"),
                    "schema_name": arguments.get("schema_name"),
                    "notebook_name": arguments.get("notebook_name"),
                    "code": arguments.get("code", ""),
                    "comment": arguments.get("comment", ""),
                }
                context = {"workspace_id": workspace_id} if workspace_id else {}
                res = execute_notebook_manager_operation("create_notebook", payload, context)
                return MCPToolResult(
                    isError=not res.get("ok", False),
                    content=[MCPToolContent(type="text", text=json.dumps(res, indent=2, default=str))],
                )

            elif name == "read_notebook":
                payload = {
                    "notebook_path": arguments.get("notebook_path"),
                    "include_outputs": arguments.get("include_outputs", True),
                }
                context = {"workspace_id": workspace_id} if workspace_id else {}
                res = execute_notebook_manager_operation("read_notebook", payload, context)
                return MCPToolResult(
                    isError=not res.get("ok", False),
                    content=[MCPToolContent(type="text", text=json.dumps(res, indent=2, default=str))],
                )

            else:
                return MCPToolResult(
                    isError=True,
                    content=[MCPToolContent(type="text", text=f"Unknown tool: {name}")],
                )
        except Exception as exc:
            logger.error("Notebook MCP tool execution error (%s): %s", name, exc)
            return MCPToolResult(
                isError=True,
                content=[MCPToolContent(type="text", text=f"Notebook tool error: {str(exc)}")],
            )
