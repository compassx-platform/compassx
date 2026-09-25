"""Built-in Native MCP Server: CompassX Dashboard Manager."""

from __future__ import annotations

import json
import logging
from typing import Any
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins.base_builtin import BaseBuiltinMCPServer
from app.ai_gateway.mcp.types import MCPTool, MCPToolResult, MCPToolContent
from app.agents.services.agent.tools.platform.dashboards.operations import (
    DASHBOARD_MANAGER_OPERATIONS,
    execute_dashboard_manager_operation,
)

logger = logging.getLogger(__name__)


class DashboardManagerMCPServer(BaseBuiltinMCPServer):
    """Native MCP Server for creating, editing, and publishing CompassX Dashboards and Widgets."""

    @property
    def name(self) -> str:
        return "compassx_dashboard_manager"

    @property
    def description(self) -> str:
        return "Create, inspect, configure widgets, add SQL datasets, and publish CompassX Dashboards."

    def list_tools(self) -> list[MCPTool]:
        return [
            MCPTool(
                name="dashboard_manage",
                description=(
                    "Execute dashboard operations. Operations include: "
                    "'list_dashboards', 'get_dashboard', 'create_dashboard', 'update_dashboard', "
                    "'add_dataset', 'update_dataset', 'delete_dataset', 'add_widget', 'update_widget', "
                    "'delete_widget', 'describe_widget', 'run_query', 'publish_dashboard'."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": DASHBOARD_MANAGER_OPERATIONS,
                            "description": "The dashboard operation to perform.",
                        },
                        "payload": {
                            "type": "object",
                            "description": "Operation-specific payload (e.g. {name, catalog_name, schema_name} or {dashboard_id, name, sql}).",
                        },
                        "context": {
                            "type": "object",
                            "description": "Optional context object.",
                        },
                    },
                    "required": ["operation", "payload"],
                },
            ),
            MCPTool(
                name="list_dashboards",
                description="List all available dashboards in the workspace.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_draft": {"type": "boolean", "description": "Include draft dashboards.", "default": True},
                        "name_filter": {"type": "string", "description": "Optional name substring filter."},
                    },
                },
            ),
            MCPTool(
                name="create_dashboard",
                description="Create a new dashboard in CompassX.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Dashboard title."},
                        "catalog_name": {"type": "string", "description": "Catalog name (default: 'main').", "default": "main"},
                        "schema_name": {"type": "string", "description": "Schema name (default: 'default').", "default": "default"},
                        "permission_mode": {"type": "string", "description": "Permission mode ('view' or 'edit').", "default": "edit"},
                    },
                    "required": ["name"],
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
            if name == "dashboard_manage":
                op = str(arguments.get("operation") or "")
                payload = arguments.get("payload") or {}
                context = arguments.get("context") or {}
                if workspace_id and "workspace_id" not in context:
                    context["workspace_id"] = workspace_id

                res = execute_dashboard_manager_operation(op, payload, context)
                return MCPToolResult(
                    isError=not res.get("ok", False),
                    content=[MCPToolContent(type="text", text=json.dumps(res, indent=2, default=str))],
                )

            elif name == "list_dashboards":
                payload = {
                    "include_draft": arguments.get("include_draft", True),
                    "name_filter": arguments.get("name_filter"),
                }
                context = {"workspace_id": workspace_id} if workspace_id else {}
                res = execute_dashboard_manager_operation("list_dashboards", payload, context)
                return MCPToolResult(
                    isError=not res.get("ok", False),
                    content=[MCPToolContent(type="text", text=json.dumps(res, indent=2, default=str))],
                )

            elif name == "create_dashboard":
                payload = {
                    "name": arguments.get("name"),
                    "catalog_name": arguments.get("catalog_name", "main"),
                    "schema_name": arguments.get("schema_name", "default"),
                    "permission_mode": arguments.get("permission_mode", "edit"),
                }
                context = {"workspace_id": workspace_id} if workspace_id else {}
                res = execute_dashboard_manager_operation("create_dashboard", payload, context)
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
            logger.error("Dashboard MCP tool execution error (%s): %s", name, exc)
            return MCPToolResult(
                isError=True,
                content=[MCPToolContent(type="text", text=f"Dashboard tool error: {str(exc)}")],
            )
