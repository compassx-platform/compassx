"""create_notebook agent tool — create a notebook inside a catalog schema.

Implements notebook creation on the catalog storage context and registers it.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult
from app.catalog.service import create_notebook, _run_async
from app.catalog.schemas import NotebookCreate

logger = logging.getLogger(__name__)


class CreateNotebookTool(BaseTool):
    """Create a new notebook registered inside a catalog schema."""

    key = "create_notebook"
    name = "Create Notebook"
    description = (
        "Create and register a new Jupyter notebook (.ipynb) inside a specific catalog and schema. "
        "The notebook will be stored in the configured storage backend for that schema/catalog."
    )
    is_async = False

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "catalog_name": {
                "type": "string",
                "description": "Name of the catalog.",
            },
            "schema_name": {
                "type": "string",
                "description": "Name of the schema within the catalog.",
            },
            "notebook_name": {
                "type": "string",
                "description": "Name of the notebook to create (alphanumeric and underscores only).",
            },
            "comment": {
                "type": "string",
                "description": "Optional description or comment for the notebook.",
            },
        },
        "required": ["catalog_name", "schema_name", "notebook_name"],
        "additionalProperties": False,
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        catalog_name = str(args["catalog_name"]).strip()
        schema_name = str(args["schema_name"]).strip()
        notebook_name = str(args["notebook_name"]).strip()
        comment = args.get("comment")

        if not catalog_name or not schema_name or not notebook_name:
            return ToolResult(ok=False, error="catalog_name, schema_name, and notebook_name are required and cannot be empty")

        user_email = agent.created_by or "system"
        user_dict = {"email": user_email, "id": user_email}

        body = NotebookCreate(
            name=notebook_name,
            comment=comment,
            initial_content=None,
        )

        from app.database import AccountSessionLocal
        account_db = AccountSessionLocal()
        try:
            notebook = _run_async(
                create_notebook(
                    db=account_db,
                    catalog_name=catalog_name,
                    schema_name=schema_name,
                    body=body,
                    user=user_dict,
                )
            )
            account_db.commit()
            return ToolResult(
                ok=True,
                result={
                    "id": notebook.id,
                    "catalog_name": notebook.catalog_name,
                    "schema_name": notebook.schema_name,
                    "name": notebook.name,
                    "blob_path": notebook.blob_path,
                    "storage_location": notebook.storage_location,
                    "owner": notebook.owner,
                    "comment": notebook.comment,
                },
            )
        except Exception as exc:
            logger.error("create_notebook tool failed: %s", exc, exc_info=True)
            return ToolResult(ok=False, error=str(exc))
        finally:
            account_db.close()
