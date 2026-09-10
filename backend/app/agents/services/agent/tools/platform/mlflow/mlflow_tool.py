from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.agents.services.agent.tools.platform.mlflow.operations import (
    MLFLOW_OPERATIONS,
    execute_mlflow_operation,
)


class MlflowTool(BaseTool):
    key = "mlflow"
    name = "MLflow"
    description = (
        "Track ML experiments and manage the model registry via an MLflow tracking server. "
        "Create/search experiments and runs, log params/metrics/models against a run, and "
        "register, version, and promote models in the model registry (stages or aliases). "
        "Requires an active 'mlflow' connection (create one under Connections); pass "
        "'connection_id' or 'connection_name' if more than one exists."
    )
    is_async = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": MLFLOW_OPERATIONS,
                "description": "The MLflow operation to execute.",
            },
            "connection_id": {
                "type": "string",
                "description": "Optional MLflow connection id, if more than one exists.",
            },
            "connection_name": {
                "type": "string",
                "description": "Optional MLflow connection name, if more than one exists.",
            },
            "payload": {
                "type": "object",
                "description": (
                    "Operation-specific arguments. Examples: "
                    "create_experiment: {name, artifact_location?, tags?}; "
                    "create_run: {experiment_id, run_name?, tags?}; "
                    "log_metric: {run_id, key, value, step?}; "
                    "log_param: {run_id, key, value}; "
                    "log_batch: {run_id, metrics?, params?, tags?}; "
                    "log_model: {run_id, artifact_path, flavor?, registered_model_name?}; "
                    "register_model: {name, source?, run_id?}; "
                    "create_model_version: {name, source, run_id?}; "
                    "transition_model_version_stage: {name, version, stage, archive_existing_versions?}; "
                    "set_registered_model_alias: {name, alias, version}; "
                    "search_runs: {experiment_ids, filter?, max_results?}; "
                    "search_model_versions: {filter?, max_results?}."
                ),
                "additionalProperties": True,
            },
            "context": {
                "type": "object",
                "description": "Optional runtime context (workspace_id, user, etc.).",
                "additionalProperties": True,
            },
        },
        "required": ["operation"],
        "additionalProperties": True,
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        operation = str(args.get("operation") or "").strip()
        payload = args.get("payload")
        context = args.get("context") or {}

        if not isinstance(payload, dict):
            payload = {}
        if not isinstance(context, dict):
            context = {}

        for key in ("connection_id", "connection_name"):
            if key in args and key not in payload:
                payload[key] = args[key]

        if agent and getattr(agent, "workspace_id", None):
            context.setdefault("workspace_id", str(agent.workspace_id))
        if agent and getattr(agent, "created_by", None):
            context.setdefault("user", str(agent.created_by))

        if not operation:
            return ToolResult(ok=False, error="Missing required parameter 'operation'", result={"ok": False, "error": "Missing required parameter 'operation'"})

        try:
            result = execute_mlflow_operation(
                operation=operation,
                payload=payload,
                context=context,
                agent=agent,
                db=db,
            )
            return ToolResult(ok=result.get("ok", False), result=result, error=result.get("error"))
        except (KeyError, TypeError, ValueError) as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
                result={"ok": False, "operation": operation, "resource_type": "mlflow", "data": None, "error": str(exc)},
            )
