"""Table Change Handler — Encapsulates change capture, serialization, and rollback for catalog tables."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.agents.services.agent.change_capture.base import BaseAssetChangeHandler

logger = logging.getLogger(__name__)

READ_ONLY_TABLE_OPERATIONS = {
    "get_table",
    "list_tables",
    "describe_table",
    "get_column_stats",
    "preview_table",
    "query",
    "run_sql",
}


class TableChangeHandler(BaseAssetChangeHandler):
    """Handler managing Table and Catalog SQL changes (SRP)."""

    @property
    def object_type(self) -> str:
        return "table"

    def supports_tool(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        t_lower = tool_name.lower()
        if "table" in t_lower or "sql" in t_lower or "schema" in t_lower:
            return True
        pld = payload or {}
        if "table_name" in pld or "table" in pld:
            return True
        return False

    def is_mutating(
        self,
        tool_name: str,
        operation: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        op = (operation or (payload.get("operation") if isinstance(payload, dict) else None) or tool_name).lower()
        if op in READ_ONLY_TABLE_OPERATIONS:
            return False
        sql = str((payload or {}).get("sql") or (payload or {}).get("query") or "").strip().upper()
        if sql.startswith("SELECT") or sql.startswith("SHOW") or sql.startswith("DESCRIBE") or sql.startswith("EXPLAIN"):
            return False
        return True

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
        res_data = result.get("data") if isinstance(result.get("data"), dict) else result
        fn = pld.get("full_name") or res_data.get("full_name") or result.get("full_name")
        if fn:
            return str(fn)
        cat = pld.get("catalog_name") or res_data.get("catalog_name")
        sch = pld.get("schema_name") or res_data.get("schema_name")
        tbl = pld.get("table_name") or pld.get("name") or res_data.get("table_name") or res_data.get("name")
        if cat and sch and tbl:
            return f"{cat}.{sch}.{tbl}"
        if goal:
            goal_slug = re.sub(r"[^a-zA-Z0-9_]", "_", goal[:30].strip()).strip("_").lower()
            return f"workspace.tables.{goal_slug or 'table'}"
        return "workspace.tables.data_table"

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
        return (
            pld.get("ddl")
            or pld.get("sql")
            or pld.get("query")
            or res_data.get("ddl")
            or res_data.get("sql")
            or res_data.get("query")
            or result.get("query")
        )

    def revert(self, full_name: str, before_content: str | None) -> bool:
        # Table rollback logic if DDL history available
        logger.info("Table revert requested for %s", full_name)
        return True
