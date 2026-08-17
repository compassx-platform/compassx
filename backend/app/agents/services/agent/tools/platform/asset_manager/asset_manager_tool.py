from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.asset_manager.schemas.agent_context import AssetManagerContextRequest
from app.asset_manager.services.agent_context_resolver import AssetManagerContextResolver
from app.asset_manager.services.agent_tools import (
    ASSET_MANAGER_OPERATIONS,
    execute_asset_manager_operation,
)


class AssetManagerTool(BaseTool):
    key = "asset_manager"
    name = "Asset Manager"
    description = (
        "Interact with platform Asset Manager functionality. Use this package tool to list, read, "
        "create, and update asset types and asset instances, and to guide safe bulk import jobs "
        "through preview, mapping, dry-run validation, approval, import, and verification. Choose "
        "one operation and pass its arguments in payload. Do not use it for destructive deletes. "
        "Only call approve_and_run_import after explicit user approval in the current turn."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ASSET_MANAGER_OPERATIONS,
                "description": "The Asset Manager operation to execute.",
            },
            "payload": {
                "type": "object",
                "description": (
                    "Operation-specific payload. Examples: "
                    "get_asset uses {asset_id}; create_asset_type uses AssetTypeCreate fields; "
                    "create_asset uses AssetInstanceCreate fields; get_import_job uses {import_job_id}; "
                    "list_uploaded_files returns attached import files after frontend upload/preview; "
                    "apply_import_mapping uses {import_job_id, field_mappings, confirmed_by_user}; "
                    "approve_and_run_import Uses {import_job_id, confirmation_statement, confirmed_by_user}; "
                    "search_asset_tags uses {asset_id, q} where q is optional search query; "
                    "search_asset_type_tags uses {type_id, q} where type_id is required and q is optional search query."
                ),
                "additionalProperties": True,
            },
            "context": {
                "type": "object",
                "description": "Optional frontend or Nova context for future integrations. Ignored in V1 unless needed.",
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
        user = getattr(agent, "created_by", None)

        if not isinstance(payload, dict):
            return ToolResult(ok=False, error="payload must be an object")
        if not isinstance(context, dict):
            return ToolResult(ok=False, error="context must be an object")

        from app.database import AssetSessionLocal
        asset_db = AssetSessionLocal()
        try:
            context = self._resolve_context(context)
            result = execute_asset_manager_operation(
                operation=operation,
                payload=payload,
                db=asset_db,
                user=user,
                context=context,
            )
            return ToolResult(ok=True, result=result)
        except HTTPException as exc:
            return ToolResult(
                ok=False,
                error=str(exc.detail),
                result={
                    "ok": False,
                    "operation": operation,
                    "resource_type": None,
                    "resource_id": None,
                    "data": None,
                    "message": None,
                    "error": str(exc.detail),
                },
            )
        except (ValueError, ValidationError) as exc:
            return ToolResult(
                ok=False,
                error=str(exc),
                result={
                    "ok": False,
                    "operation": operation,
                    "resource_type": None,
                    "resource_id": None,
                    "data": None,
                    "message": None,
                    "error": str(exc),
                },
            )
        finally:
            asset_db.close()

    def _resolve_context(self, context: dict[str, Any]) -> dict[str, Any]:
        raw_asset_context = context.get("asset_manager")
        if not isinstance(raw_asset_context, dict):
            return context
        resolved = AssetManagerContextResolver().resolve(
            AssetManagerContextRequest.model_validate(raw_asset_context)
        )
        return {**context, **resolved}
