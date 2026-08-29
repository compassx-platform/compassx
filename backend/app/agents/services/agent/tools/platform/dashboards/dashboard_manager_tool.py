from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.platform.dashboards.operations import (
    DASHBOARD_MANAGER_OPERATIONS,
    execute_dashboard_manager_operation,
)


class DashboardManagerTool(BaseTool):
    key = "dashboard_manager"
    name = "Dashboard Manager"
    description = (
        "Interact with platform dashboards through one unified tool. "
        "Use this tool to list, inspect, create, and configure dashboards — "
        "inspect widget schemas (describe_widget), add SQL datasets, add and configure chart/table/card widgets, "
        "run SQL previews to validate data, and publish the finished dashboard. "
        "Choose one operation and pass its arguments in payload."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": DASHBOARD_MANAGER_OPERATIONS,
                "description": (
                    "The Dashboard Manager operation to execute. "
                    "Typical workflow: list_dashboards → create_dashboard → update_dashboard (optional page structure) → "
                    "run_query (validate SQL) → add_dataset → describe_widget (inspect widget schema) → "
                    "add_widget → update_widget → publish_dashboard."
                ),
            },
            "payload": {
                "type": "object",
                "description": (
                    "Operation-specific payload. Examples: "
                    "describe_widget uses {chart_type: 'counter'|'bar'|'line'|'table'|'pie'|'combo'|'waterfall'|'pivot'}; "
                    "list_dashboards uses {include_draft, name_filter}; "
                    "get_dashboard uses {dashboard_id}; "
                    "create_dashboard uses {name, catalog_name, schema_name, permission_mode}; "
                    "update_dashboard uses {dashboard_id, name, pages: ['Page 1', 'Page 2'], settings}; "
                    "add_dataset uses {dashboard_id, name, sql, params}; "
                    "update_dataset uses {dashboard_id, dataset_id, sql}; "
                    "add_widget uses {dashboard_id, page_id, widget_type: 'chart', title, chart_config: {chartType, datasetId, xField, yFields, title_row_bg}, grid_item}; "
                    "update_widget uses {dashboard_id, widget_id, title, chart_config}; "
                    "run_query uses {sql, max_rows, warehouse_id}; "
                    "publish_dashboard uses {dashboard_id}."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["operation", "payload"],
        "additionalProperties": False,
    }


    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        operation = str(args.get("operation") or "")
        payload = args.get("payload") or {}

        if not isinstance(payload, dict):
            return ToolResult(ok=False, error="payload must be an object")

        # Security context is backend-owned; never trust model-supplied workspace or user values.
        workspace_id = getattr(agent, "workspace_id", None)
        if not workspace_id:
            return ToolResult(ok=False, error="Dashboard operations require a workspace-scoped agent")
        context = {
            "workspace_id": str(workspace_id),
            "user": getattr(agent, "created_by", None) or "agent",
        }
        if payload.get("warehouse_id"):
            context["warehouse_id"] = payload["warehouse_id"]


        try:
            result = execute_dashboard_manager_operation(
                operation=operation,
                payload=payload,
                context=context,
            )
            return ToolResult(ok=result["ok"], result=result, error=result.get("error"))
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
                result={
                    "ok": False,
                    "operation": operation,
                    "resource_type": "dashboard",
                    "resource_id": payload.get("dashboard_id"),
                    "data": None,
                    "message": None,
                    "error": str(exc),
                },
            )
