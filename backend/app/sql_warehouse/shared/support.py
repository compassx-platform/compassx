"""Shared request identity and query-history presentation."""
from typing import Any

from fastapi import Request

from app.sql_warehouse.models import SqlQueryRecord


def _resolve_user_and_workspace(request: Request, user: Any = None) -> tuple[str, str | None]:
    ws_ctx = getattr(request.state, "workspace", None)
    workspace_id = ws_ctx.workspace_id if ws_ctx and hasattr(ws_ctx, "workspace_id") else None
    if not workspace_id:
        workspace_id = request.headers.get("X-Workspace-Id") or request.query_params.get("workspace_id")

    user_id = None
    if ws_ctx and getattr(ws_ctx, "principal_id", None):
        user_id = ws_ctx.principal_id
    elif isinstance(user, dict):
        user_id = user.get("id") or user.get("sub")
    elif hasattr(user, "id"):
        user_id = user.id

    if not user_id:
        user_id = "bbbbbbbb-0000-0000-0000-000000000001"

    return str(user_id), str(workspace_id) if workspace_id else None


def _record_to_dict(record: SqlQueryRecord) -> dict:
    return {
        "id": record.id,
        "warehouse_id": record.warehouse_id,
        "session_id": record.session_id,
        "user_id": record.user_id,
        "sql_text": record.sql_text,
        "sql_hash": record.sql_hash,
        "status": record.status,
        "engine": record.engine,
        "source": record.source,
        "dashboard_id": record.dashboard_id,
        "dataset_id": record.dataset_id,
        "run_by_user_id": record.run_by_user_id,
        "run_by_user_name": record.run_by_user_name,
        "rows_returned": record.rows_returned,
        "bytes_scanned": record.bytes_scanned,
        "duration_ms": record.duration_ms,
        "error_message": record.error_message,
        "cache_hit": record.cache_hit,
        "query_analysis": record.query_analysis,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "created_at": record.created_at,
    }
