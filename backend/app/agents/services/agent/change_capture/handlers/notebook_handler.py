"""Notebook Change Handler — Encapsulates change capture, serialization, and rollback for Notebooks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Optional

from app.agents.services.agent.change_capture.base import BaseAssetChangeHandler

logger = logging.getLogger(__name__)

READ_ONLY_NOTEBOOK_OPERATIONS = {
    "read_notebook",
    "get_cell",
    "inspect_notebook",
    "run_cell",
    "run_all_cells",
    "execute_cell",
    "approve_cell_edit",
    "reject_cell_edit",
}

MUTATING_NOTEBOOK_OPERATIONS = {
    "create_notebook",
    "edit_cell",
    "propose_cell_edit",
    "apply_notebook_edit",
    "add_multiple_cells",
    "add_cells",
    "create_cell",
    "insert_cell",
    "delete_cell",
    "append_to_cell",
}


class NotebookChangeHandler(BaseAssetChangeHandler):
    """Handler managing Notebook asset changes (SRP)."""

    @property
    def object_type(self) -> str:
        return "notebook"

    def supports_tool(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        t_lower = tool_name.lower()
        if "notebook" in t_lower or t_lower == "catalog_editor":
            return True
        if operation and (operation in MUTATING_NOTEBOOK_OPERATIONS or operation in READ_ONLY_NOTEBOOK_OPERATIONS):
            return True
        pld = payload or {}
        if pld.get("notebook_path") or (isinstance(pld.get("path"), str) and pld["path"].endswith(".ipynb")):
            return True
        return False

    def is_mutating(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        op = (operation or (payload.get("operation") if isinstance(payload, dict) else None) or tool_name).lower()
        if op in READ_ONLY_NOTEBOOK_OPERATIONS:
            return False
        if op in MUTATING_NOTEBOOK_OPERATIONS or "edit" in op or "create" in op or "add" in op or "insert" in op or "delete" in op:
            return True
        return False

    def resolve_full_name(
        self,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
        goal: str | None = None,
    ) -> str | None:
        pld = payload or {}
        ctx = context or {}
        res_data = result.get("data") if isinstance(result.get("data"), dict) else result

        # 1. Check explicit full_name or paths
        fn = (
            result.get("full_name")
            or pld.get("full_name")
            or pld.get("notebook_path")
            or ctx.get("notebook_path")
            or ctx.get("path")
            or pld.get("path")
            or res_data.get("full_name")
            or res_data.get("notebook_path")
        )
        if fn:
            return str(fn)

        # 2. Check catalog coordinates
        cat = pld.get("catalog_name") or res_data.get("catalog_name")
        sch = pld.get("schema_name") or res_data.get("schema_name")
        nm = pld.get("notebook_name") or pld.get("name") or res_data.get("notebook_name") or res_data.get("name")
        if cat and sch and nm:
            return f"{cat}.{sch}.{nm}"

        # 3. Fallback to goal slug
        if goal:
            goal_slug = re.sub(r"[^a-zA-Z0-9_]", "_", goal[:30].strip()).strip("_").lower()
            return f"workspace.notebooks.{goal_slug or 'analysis_notebook'}"

        return "workspace.notebooks.analysis_notebook"

    def serialize_current_state(
        self,
        full_name: str,
        tool_name: str,
        operation: str | None,
        payload: dict[str, Any],
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str | None:
        pld = payload or {}
        res_data = result.get("data") if isinstance(result.get("data"), dict) else result

        # Check direct content in result or payload
        after = (
            result.get("after_content")
            or result.get("content")
            or result.get("code")
            or pld.get("code")
            or pld.get("source")
            or pld.get("content")
            or res_data.get("code")
            or res_data.get("source")
            or res_data.get("content")
            or (result.get("notebook_content") if isinstance(result, dict) else None)
        )
        if after and isinstance(after, str):
            return after

        # Check cells array
        cells = pld.get("cells") or res_data.get("cells")
        if isinstance(cells, list):
            c_texts = [
                c.get("code") or c.get("source")
                for c in cells
                if isinstance(c, dict) and (c.get("code") or c.get("source"))
            ]
            if c_texts:
                return "\n\n".join(c_texts)

        if "comment" in pld:
            return f"# Notebook created\n# Comment: {pld.get('comment')}"

        return None

    def revert(self, full_name: str, before_content: str | None) -> bool:
        try:
            # 1. Catalog notebook in UnifiedCatalog
            dot_parts = full_name.split(".")
            if len(dot_parts) == 3 and not full_name.endswith(".ipynb"):
                try:
                    from app.database import AccountSessionLocal
                    from app.catalog.models import UnifiedCatalogNotebook, UnifiedCatalogSchema
                    from app.catalog.service import _write_notebook_content

                    with AccountSessionLocal() as account_db:
                        nb = account_db.query(UnifiedCatalogNotebook).filter(
                            UnifiedCatalogNotebook.catalog_name == dot_parts[0],
                            UnifiedCatalogNotebook.schema_name == dot_parts[1],
                            UnifiedCatalogNotebook.name == dot_parts[2],
                        ).first()
                        if nb and nb.blob_path:
                            schema = account_db.query(UnifiedCatalogSchema).filter(
                                UnifiedCatalogSchema.catalog_name == dot_parts[0],
                                UnifiedCatalogSchema.name == dot_parts[1],
                            ).first()
                            if schema:
                                if before_content:
                                    try:
                                        nb_data = json.loads(before_content)
                                    except Exception:
                                        nb_data = {
                                            "nbformat": 4,
                                            "nbformat_minor": 5,
                                            "metadata": {},
                                            "cells": [{
                                                "cell_type": "code",
                                                "source": before_content,
                                                "metadata": {},
                                                "outputs": [],
                                                "execution_count": None,
                                            }],
                                        }
                                else:
                                    nb_data = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []}

                                try:
                                    loop = asyncio.get_event_loop()
                                    if loop.is_running():
                                        import concurrent.futures
                                        with concurrent.futures.ThreadPoolExecutor() as pool:
                                            pool.submit(asyncio.run, _write_notebook_content(account_db, schema, nb.blob_path, nb_data)).result()
                                    else:
                                        loop.run_until_complete(_write_notebook_content(account_db, schema, nb.blob_path, nb_data))
                                except Exception:
                                    asyncio.run(_write_notebook_content(account_db, schema, nb.blob_path, nb_data))
                                return True
                except Exception as nb_err:
                    logger.debug("Catalog notebook revert attempt: %s", nb_err)

            # 2. Local file on disk or workspace
            path_obj = Path(full_name)
            if path_obj.is_absolute() or path_obj.exists():
                if before_content is not None:
                    path_obj.parent.mkdir(parents=True, exist_ok=True)
                    path_obj.write_text(before_content, encoding="utf-8")
                else:
                    if path_obj.is_file():
                        path_obj.unlink(missing_ok=True)
                return True

            workspace_root = Path(os.environ.get("AGENT_WORKSPACE_ROOT", str(Path(tempfile.gettempdir()) / "agent_workspaces")))
            if workspace_root.exists():
                clean_rel = full_name.lstrip("/\\")
                matched_files = list(workspace_root.glob(f"**/{clean_rel}"))
                for mf in matched_files:
                    if before_content is not None:
                        mf.write_text(before_content, encoding="utf-8")
                    else:
                        if mf.is_file():
                            mf.unlink(missing_ok=True)
                    return True

        except Exception as exc:
            logger.exception("Failed reverting notebook content for %s: %s", full_name, exc)
            return False
        return False
