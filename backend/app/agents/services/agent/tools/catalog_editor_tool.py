"""catalog_editor agent tool — create, edit, and delete schemas in the catalog."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogNotebook
from app.catalog.service import create_schema, delete_schema, create_volume, _run_async
from app.catalog.schemas import SchemaCreate, VolumeCreate

logger = logging.getLogger(__name__)


class CatalogEditorTool(BaseTool):
    """Create, edit, and delete schema/volume metadata directly in the catalog database."""

    key = "catalog_editor"
    name = "Catalog Editor"
    description = (
        "Create, edit, and delete schemas and volumes in the CompassX catalog database. "
        "Choose one operation and pass its arguments in payload."
    )
    is_async = False

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["create_schema", "update_schema", "delete_schema", "create_volume"],
                "description": "The catalog editor operation to execute.",
            },
            "payload": {
                "type": "object",
                "description": "Operation-specific parameters.",
                "properties": {
                    "catalog_name": {
                        "type": "string",
                        "description": "Name of the catalog.",
                    },
                    "schema_name": {
                        "type": "string",
                        "description": "Name of the schema.",
                    },
                    "volume_name": {
                        "type": "string",
                        "description": "Name of the volume (used in 'create_volume').",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description for the schema/volume (used in 'create_schema', 'update_schema', and 'create_volume').",
                    },
                },
                "required": ["catalog_name", "schema_name"],
                "additionalProperties": False,
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

        catalog_name = str(payload.get("catalog_name") or "").strip()
        schema_name = str(payload.get("schema_name") or "").strip()
        volume_name = str(payload.get("volume_name") or "").strip()
        description = payload.get("description")

        if not catalog_name or not schema_name:
            return ToolResult(ok=False, error="catalog_name and schema_name are required parameters.")

        from app.database import AccountSessionLocal
        account_db = AccountSessionLocal()

        user_email = agent.created_by or "system"
        user_dict = {"email": user_email, "id": user_email}

        try:
            if operation == "create_schema":
                body = SchemaCreate(name=schema_name, description=description)
                schema = create_schema(db=account_db, catalog_name=catalog_name, body=body, user=user_dict)
                account_db.commit()
                return ToolResult(
                    ok=True,
                    result={
                        "operation": operation,
                        "schema": {
                            "id": schema.id,
                            "catalog_id": schema.catalog_id,
                            "name": schema.name,
                            "description": schema.description,
                            "created_by": schema.created_by,
                        },
                    },
                )

            elif operation == "update_schema":
                catalog = account_db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
                if not catalog:
                    return ToolResult(ok=False, error=f"Catalog '{catalog_name}' not found.")
                schema = account_db.query(UnifiedCatalogSchema).filter(
                    UnifiedCatalogSchema.catalog_id == catalog.id,
                    UnifiedCatalogSchema.name == schema_name
                ).first()
                if not schema:
                    return ToolResult(ok=False, error=f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

                schema.description = description
                account_db.commit()
                account_db.refresh(schema)
                return ToolResult(
                    ok=True,
                    result={
                        "operation": operation,
                        "schema": {
                            "id": schema.id,
                            "catalog_id": schema.catalog_id,
                            "name": schema.name,
                            "description": schema.description,
                        },
                    },
                )

            elif operation == "delete_schema":
                delete_schema(db=account_db, catalog_name=catalog_name, schema_name=schema_name)
                return ToolResult(
                    ok=True,
                    result={
                        "operation": operation,
                        "catalog_name": catalog_name,
                        "schema_name": schema_name,
                        "status": "deleted",
                    },
                )

            elif operation == "create_volume":
                if not volume_name:
                    return ToolResult(ok=False, error="volume_name is required for create_volume operation.")
                body_volume = VolumeCreate(name=volume_name, description=description)
                volume = _run_async(
                    create_volume(
                        db=account_db,
                        catalog_name=catalog_name,
                        schema_name=schema_name,
                        body=body_volume,
                        user=user_dict,
                    )
                )
                account_db.commit()
                return ToolResult(
                    ok=True,
                    result={
                        "operation": operation,
                        "volume": {
                            "id": volume.id,
                            "schema_id": volume.schema_id,
                            "name": volume.name,
                            "description": volume.description,
                            "storage_location": volume.storage_location,
                            "owner": volume.owner,
                            "created_by": volume.created_by,
                        },
                    },
                )

            else:
                return ToolResult(ok=False, error=f"Unsupported catalog_editor operation: {operation}")

        except Exception as exc:
            logger.error("catalog_editor operation %s failed: %s", operation, exc, exc_info=True)
            return ToolResult(ok=False, error=str(exc))
        finally:
            account_db.close()
