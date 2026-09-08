from __future__ import annotations

from typing import Any

from app.nova.services.notebook_tools import NOTEBOOK_NOVA_TOOLS

NOTEBOOK_MANAGER_OPERATIONS = [tool.key for tool in NOTEBOOK_NOVA_TOOLS]

_NOTEBOOK_TOOL_MAP = {tool.key: tool for tool in NOTEBOOK_NOVA_TOOLS}


def _resource_id(context: dict[str, Any] | None) -> Any:
    context = context or {}
    notebook = context.get("notebook")
    if isinstance(notebook, dict):
        return (
            notebook.get("notebook_id")
            or notebook.get("notebook_path")
            or notebook.get("path")
        )
    return context.get("notebook_id") or context.get("path")


def execute_notebook_manager_operation(
    operation: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool = _NOTEBOOK_TOOL_MAP.get(operation)
    if tool is None:
        raise ValueError(f"Unsupported notebook_manager operation: {operation}")

    ctx = dict(context or {})
    for k in ("notebook_id", "notebook_path", "path", "notebook_name"):
        if k in payload and k not in ctx:
            ctx[k] = payload[k]

    result = tool.execute(payload, ctx)
    return {
        "ok": result.ok,
        "operation": operation,
        "resource_type": "notebook",
        "resource_id": _resource_id(ctx),
        "data": result.result if result.ok else None,
        "message": None,
        "error": result.error,
    }
