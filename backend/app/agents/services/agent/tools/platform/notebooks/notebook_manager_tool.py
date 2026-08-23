from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.platform.notebooks.operations import (
    NOTEBOOK_MANAGER_OPERATIONS,
    execute_notebook_manager_operation,
)


class NotebookManagerTool(BaseTool):
    key = "notebook_manager"
    name = "Notebook Manager"
    description = (
        "Interact with notebook-level functionality through one package tool. Use this tool to inspect "
        "cell outputs, variable state, schema hints, imports, or another referenced notebook; request "
        "notebook cell execution; and return notebook edits. "
        "When writing cells that produce data to be saved as Catalog tables, use cx.write_table(df, 'catalog.schema.table', mode='overwrite'|'append') or df.write_table(...). "
        "Choose one operation and pass its arguments in payload."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": NOTEBOOK_MANAGER_OPERATIONS,
                "description": "The Notebook Manager operation to execute.",
            },
            "payload": {
                "type": "object",
                "description": (
                    "Operation-specific payload. Examples: get_cell_output uses {cell_index}; "
                    "get_variable_state uses {cell_index, variable_name}; get_schema uses "
                    "{table_or_view_name}; list_imports uses {}; read_notebook uses "
                    "{notebook_path, include_outputs, max_cells}; run_cell uses "
                    "{cell_index, cell_indices, run_all}; "
                    "edit_cell uses {cell_index, cell_type, code, explanation}; "
                    "add_multiple_cells uses {insert_after_cell_index, cells: [{cell_type, code, explanation}], explanation}. "
                    "In generated Python code cells, use cx.write_table(df, 'catalog.schema.table', mode='overwrite') to persist tables into the Catalog."
                ),
                "additionalProperties": True,
            },
            "context": {
                "type": "object",
                "description": (
                    "Notebook context from the frontend or runtime, such as cells, variable_state, "
                    "schema_hints, imports, notebook_id, or path."
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

        if agent and getattr(agent, "workspace_id", None):
            context.setdefault("workspace_id", str(agent.workspace_id))

        try:
            result = execute_notebook_manager_operation(
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
                    "resource_type": "notebook",
                    "resource_id": context.get("notebook_id") or context.get("path"),
                    "data": None,
                    "message": None,
                    "error": str(exc),
                },
            )
