from __future__ import annotations

from typing import Any

from app.nova.services.dashboard_tools import DASHBOARD_NOVA_TOOLS

DASHBOARD_MANAGER_OPERATIONS = [tool.key for tool in DASHBOARD_NOVA_TOOLS]

_DASHBOARD_TOOL_MAP = {tool.key: tool for tool in DASHBOARD_NOVA_TOOLS}


def _resource_id(payload: dict[str, Any] | None, context: dict[str, Any] | None) -> Any:
    payload = payload or {}
    context = context or {}
    return (
        payload.get("dashboard_id")
        or payload.get("dashboardId")
        or context.get("dashboard_id")
        or context.get("dashboardId")
    )


def execute_dashboard_manager_operation(
    operation: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool = _DASHBOARD_TOOL_MAP.get(operation)
    if tool is None:
        raise ValueError(f"Unsupported dashboard_manager operation: {operation!r}")

    result = tool.execute(payload, context or {})
    return {
        "ok": result.ok,
        "operation": operation,
        "resource_type": "dashboard",
        "resource_id": _resource_id(payload, context),
        "data": result.result if result.ok else None,
        "message": None,
        "error": result.error,
    }
