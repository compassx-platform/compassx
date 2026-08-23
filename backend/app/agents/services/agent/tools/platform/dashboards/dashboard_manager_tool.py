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
                    "Typical workflow: list_dashboards → create_dashboard → update_dashboard (pages) → "
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
                    "create_dashboard uses {name, permission_mode}; "
                    "update_dashboard uses {dashboard_id, name, pages: ['Page 1', 'Page 2'], settings}; "
                    "add_dataset uses {dashboard_id, name, sql, params}; "
                    "update_dataset uses {dashboard_id, dataset_id, sql}; "
                    "add_widget uses {dashboard_id, page_id, widget_type: 'chart', title, chart_config: {chartType, datasetId, xField, yFields}, grid_item}; "
                    "update_widget uses {dashboard_id, widget_id, title, chart_config}; "
                    "run_query uses {sql, max_rows, warehouse_id}; "
                    "publish_dashboard uses {dashboard_id}."
                ),
                "additionalProperties": True,
            },
            "context": {
                "type": "object",
                "description": (
                    "Optional runtime context, such as workspace_id, warehouse_id, or user. "
                    "Passed through to operations that need workspace or warehouse resolution."
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
        context = args.get("context") or {}

        if not isinstance(payload, dict):
            return ToolResult(ok=False, error="payload must be an object")
        if not isinstance(context, dict):
            return ToolResult(ok=False, error="context must be an object")

        # Inject agent identity into context for audit / created_by tracking
        if not context.get("user") and hasattr(agent, "created_by"):
            context = {**context, "user": agent.created_by}

        # Inject agent workspace_id into context to ensure catalog & workspace binding
        if not context.get("workspace_id") and getattr(agent, "workspace_id", None):
            context = {**context, "workspace_id": str(agent.workspace_id)}


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
