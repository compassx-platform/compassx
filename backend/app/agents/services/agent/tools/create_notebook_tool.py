"""create_notebook agent tool — create a notebook inside a catalog schema.

Implements notebook creation on the catalog storage context and registers it.
"""
from __future__ import annotations

import json
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
        "You can supply the executable Python code directly via the 'code' parameter or 'cells' list. "
        "The notebook runtime has 'import services.compassx_sql as cx' pre-imported. "
        "To save DataFrames as Catalog tables (Iceberg or Postgres), use cx.write_table(df, 'catalog.schema.table', mode='overwrite'|'append') or df.write_table(...). "
        "To query registered tables, use cx.sql('SELECT ...')."
    )
    is_async = False

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "catalog_name": {
                "type": "string",
                "description": "Name of the catalog (e.g. 'test_default', 'main', 'workspace').",
            },
            "schema_name": {
                "type": "string",
                "description": "Name of the schema within the catalog (e.g. 'default', 'dgr_synthetic').",
            },
            "notebook_name": {
                "type": "string",
                "description": "Name of the notebook to create (alphanumeric and underscores only).",
            },
            "comment": {
                "type": "string",
                "description": "Optional description or comment for the notebook.",
            },
            "code": {
                "type": "string",
                "description": (
                    "Executable Python code to populate the primary code cell in the notebook. "
                    "Use cx.write_table(df, 'catalog.schema.table', mode='overwrite') or df.write_table(...) to register and persist DataFrames to Catalog tables."
                ),
            },
            "cells": {
                "type": "array",
                "description": "Optional list of cell objects: [{cell_type: 'code'|'markdown', code: '...'}]",
                "items": {
                    "type": "object",
                    "properties": {
                        "cell_type": {"type": "string", "enum": ["code", "markdown", "raw"]},
                        "code": {"type": "string"},
                    },
                    "required": ["code"],
                },
            },
        },
        "required": ["catalog_name", "schema_name", "notebook_name"],
        "additionalProperties": True,
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        catalog_name = str(args.get("catalog_name", "")).strip()
        schema_name = str(args.get("schema_name", "")).strip()
        notebook_name = str(args.get("notebook_name", "")).strip()
        comment = args.get("comment")
        code = args.get("code") or args.get("notebook_content")
        cells = args.get("cells")

        if not catalog_name or not schema_name or not notebook_name:
            return ToolResult(ok=False, error="catalog_name, schema_name, and notebook_name are required and cannot be empty")

        user_email = agent.created_by or "system"
        user_dict = {"email": user_email, "id": user_email}

        # Build initial ipynb JSON payload
        initial_content: dict[str, Any] | None = None
        if cells and isinstance(cells, list):
            formatted_cells = []
            for c in cells:
                if not isinstance(c, dict):
                    continue
                ctype = c.get("cell_type", "code")
                src = c.get("code") or c.get("source") or ""
                formatted_cells.append({
                    "cell_type": ctype,
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [src] if isinstance(src, str) else src,
                })
            initial_content = {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "cells": formatted_cells,
            }
        elif code and isinstance(code, str):
            initial_content = {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [code],
                    }
                ],
            }

        body = NotebookCreate(
            name=notebook_name,
            comment=comment,
            initial_content=initial_content,
        )

        from app.database import AccountSessionLocal
        from app.catalog.models import UnifiedCatalog
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
            full_name = f"{notebook.catalog_name}.{notebook.schema_name}.{notebook.name}"
            return ToolResult(
                ok=True,
                result={
                    "id": notebook.id,
                    "full_name": full_name,
                    "catalog_name": notebook.catalog_name,
                    "schema_name": notebook.schema_name,
                    "name": notebook.name,
                    "blob_path": notebook.blob_path,
                    "storage_location": notebook.storage_location,
                    "owner": notebook.owner,
                    "comment": notebook.comment,
                    "cells_count": len(initial_content["cells"]) if initial_content else 0,
                    "code": code if code else (cells[0].get("code") if cells else None),
                },
            )
        except Exception as exc:
            logger.error("create_notebook tool failed: %s", exc, exc_info=True)
            return ToolResult(ok=False, error=str(exc))
        finally:
            account_db.close()
