from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from typing import Any

from sqlalchemy.orm import Session

from app.models.agents import Agent
from app.database import SystemSessionLocal
from app.sql_warehouse.warehouse.manager import list_warehouses, get_warehouse_by_id
from app.sql_warehouse.engine.router import get_adapter
from app.sql_warehouse.query.executor import QueryExecutor
from app.sql_warehouse.query.query_record import QueryRecordStore

logger = logging.getLogger(__name__)

SQL_WAREHOUSE_OPERATIONS = [
    "execute_query",
    "run_query",
    "list_warehouses",
    "get_warehouse",
    "explain_query",
    "get_query_history",
    "get_query_result",
]


def _run_async(coro):
    """Run an async coroutine synchronously from sync tool execution."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        future = Future()

        def _run():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(coro)
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
            finally:
                new_loop.close()

        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return future.result()
    else:
        return loop.run_until_complete(coro)


def _resolve_workspace_id(context: dict[str, Any] | None, agent: Agent | None) -> str | None:
    context = context or {}
    ws_id = context.get("workspace_id") or context.get("workspace")
    if not ws_id and agent and getattr(agent, "workspace_id", None):
        ws_id = str(agent.workspace_id)
    return str(ws_id) if ws_id else None


def _resolve_warehouse(
    system_db: Session,
    warehouse_id: str | None,
    workspace_id: str | None,
) -> tuple[Any | None, str | None]:
    """Find target warehouse by ID or fallback to the running/default warehouse."""
    all_whs = list_warehouses(system_db, workspace_id=workspace_id)
    
    if warehouse_id:
        # Match by ID or name
        wh = get_warehouse_by_id(system_db, str(warehouse_id), workspace_id=workspace_id)
        if not wh:
            # Try name match
            wh = next((w for w in all_whs if w.name.lower() == str(warehouse_id).lower()), None)
        if not wh:
            available_names = [f"{w.name} ({w.id}, {w.status})" for w in all_whs]
            return None, f"Warehouse '{warehouse_id}' not found. Available warehouses: {available_names or 'None'}"
        return wh, None

    if not all_whs:
        # Fallback to global warehouses
        if workspace_id:
            all_whs = list_warehouses(system_db, workspace_id=None)

    if not all_whs:
        return None, "No SQL warehouses configured in this workspace. Please create a warehouse in the SQL Warehouse module."

    # Prefer a running warehouse
    running = next((w for w in all_whs if w.status == "running"), None)
    if running:
        return running, None

    # If all stopped, return the first one with a note
    first = all_whs[0]
    return first, None


def execute_sql_query(
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Execute a SQL query against the warehouse and record execution history."""
    sql = str(payload.get("sql") or payload.get("query") or "").strip()
    if not sql:
        return {"ok": False, "error": "Missing required parameter 'sql'"}

    warehouse_id = payload.get("warehouse_id") or payload.get("warehouse")
    catalog = payload.get("catalog") or payload.get("catalog_name")
    schema_name = payload.get("schema_name") or payload.get("schema")
    max_rows = min(max(int(payload.get("max_rows", 1000)), 1), 10000)

    workspace_id = _resolve_workspace_id(context, agent)
    system_db = SystemSessionLocal()
    try:
        warehouse, err = _resolve_warehouse(system_db, warehouse_id, workspace_id)
        if err:
            return {"ok": False, "error": err}
        if not warehouse:
            return {"ok": False, "error": "No SQL warehouse found"}

        if warehouse.status != "running":
            return {
                "ok": False,
                "error": f"Warehouse '{warehouse.name}' ({warehouse.id}) is currently {warehouse.status}. Please start the warehouse in the SQL Warehouse page before executing queries.",
            }

        user_id = str((agent.created_by if agent else None) or (context or {}).get("user") or "agent")
        run_by_user_id = str(agent.created_by if agent and agent.created_by else user_id)
        run_by_user_name = getattr(agent, "name", "AI Agent")

        executor = QueryExecutor(system_db, system_db)
        result = _run_async(
            executor.run(
                warehouse=warehouse,
                sql=sql,
                user_id=user_id,
                session_id=None,
                max_rows=max_rows,
                catalog=catalog,
                schema_name=schema_name,
                source="agent",
                run_by_user_id=run_by_user_id,
                run_by_user_name=run_by_user_name,
            )
        )

        rows = result.get("rows", [])
        return {
            "ok": True,
            "query_id": result.get("query_id"),
            "columns": result.get("columns", []),
            "rows": rows,
            "rowCount": len(rows),
            "rows_returned": len(rows),
            "truncated": result.get("truncated", False),
            "duration_ms": result.get("duration_ms", 0),
            "execution_time_ms": result.get("duration_ms", 0),
            "cache_hit": result.get("cache_hit", False),
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "engine": warehouse.engine,
            "query_analysis": result.get("query_analysis"),
        }
    except Exception as exc:
        logger.exception("Warehouse query execution failed: %s", exc)
        return {"ok": False, "error": f"Query execution failed: {exc}"}
    finally:
        system_db.close()


def list_sql_warehouses(
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """List SQL warehouses available in the workspace."""
    workspace_id = _resolve_workspace_id(context, agent)
    system_db = SystemSessionLocal()
    try:
        warehouses = list_warehouses(system_db, workspace_id=workspace_id)
        # If workspace-filtered list is empty, include global warehouses
        if not warehouses and workspace_id:
            warehouses = list_warehouses(system_db, workspace_id=None)

        items = [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "engine": w.engine,
                "status": w.status,
                "resource_policy": w.resource_policy or {},
                "created_at": w.created_at.isoformat() if hasattr(w, "created_at") and w.created_at else None,
            }
            for w in warehouses
        ]
        return {"ok": True, "warehouses": items, "count": len(items)}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to list warehouses: {exc}"}
    finally:
        system_db.close()


def get_sql_warehouse_details(
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Get details for a specific warehouse."""
    warehouse_id = payload.get("warehouse_id") or payload.get("id")
    if not warehouse_id:
        return {"ok": False, "error": "Missing required parameter 'warehouse_id'"}

    workspace_id = _resolve_workspace_id(context, agent)
    system_db = SystemSessionLocal()
    try:
        warehouse, err = _resolve_warehouse(system_db, str(warehouse_id), workspace_id)
        if err:
            return {"ok": False, "error": err}
        if not warehouse:
            return {"ok": False, "error": f"Warehouse '{warehouse_id}' not found"}

        return {
            "ok": True,
            "warehouse": {
                "id": warehouse.id,
                "name": warehouse.name,
                "description": warehouse.description,
                "engine": warehouse.engine,
                "status": warehouse.status,
                "config": warehouse.config or {},
                "resource_policy": warehouse.resource_policy or {},
            },
        }
    except Exception as exc:
        return {"ok": False, "error": f"Failed to get warehouse details: {exc}"}
    finally:
        system_db.close()


def explain_sql_query(
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Explain execution plan for a SQL query."""
    sql = str(payload.get("sql") or payload.get("query") or "").strip()
    if not sql:
        return {"ok": False, "error": "Missing required parameter 'sql'"}

    warehouse_id = payload.get("warehouse_id")
    workspace_id = _resolve_workspace_id(context, agent)
    system_db = SystemSessionLocal()
    try:
        warehouse, err = _resolve_warehouse(system_db, warehouse_id, workspace_id)
        if err:
            return {"ok": False, "error": err}
        if not warehouse:
            return {"ok": False, "error": "No SQL warehouse available"}

        adapter = get_adapter(warehouse)
        plan = _run_async(adapter.explain(sql))
        return {
            "ok": True,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "engine": warehouse.engine,
            "plan": plan,
        }
    except Exception as exc:
        return {"ok": False, "error": f"Failed to explain query: {exc}"}
    finally:
        system_db.close()


def get_query_history(
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Fetch recent query history recorded in the SQL warehouse audit store."""
    warehouse_id = payload.get("warehouse_id")
    limit = min(max(int(payload.get("limit", 20)), 1), 100)
    offset = max(int(payload.get("offset", 0)), 0)
    status = payload.get("status")

    system_db = SystemSessionLocal()
    try:
        records = QueryRecordStore(system_db).list(
            warehouse_id=str(warehouse_id) if warehouse_id else None,
            status=status,
            limit=limit,
            offset=offset,
        )
        items = [
            {
                "id": r.id,
                "warehouse_id": r.warehouse_id,
                "sql_text": r.sql_text,
                "status": r.status,
                "engine": r.engine,
                "source": r.source,
                "rows_returned": r.rows_returned,
                "bytes_scanned": r.bytes_scanned,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
                "cache_hit": r.cache_hit,
                "created_at": r.created_at.isoformat() if hasattr(r, "created_at") and r.created_at else None,
            }
            for r in records
        ]
        return {"ok": True, "records": items, "count": len(items)}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to get query history: {exc}"}
    finally:
        system_db.close()


def get_query_result_by_id(
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Retrieve saved result payload for a previously executed query ID."""
    query_id = payload.get("query_id") or payload.get("id")
    if not query_id:
        return {"ok": False, "error": "Missing required parameter 'query_id'"}

    system_db = SystemSessionLocal()
    try:
        record = QueryRecordStore(system_db).get(str(query_id))
        if not record:
            return {"ok": False, "error": f"Query ID '{query_id}' not found"}

        if record.result_payload:
            return {
                "ok": True,
                "query_id": str(query_id),
                "status": record.status,
                "cache_hit": record.cache_hit,
                "query_analysis": record.query_analysis,
                **record.result_payload,
            }
        return {
            "ok": True,
            "query_id": str(query_id),
            "status": record.status,
            "message": "Result payload is no longer in cache. Please re-run the query.",
        }
    except Exception as exc:
        return {"ok": False, "error": f"Failed to retrieve query result: {exc}"}
    finally:
        system_db.close()


def execute_sql_warehouse_operation(
    operation: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    agent: Agent | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    """Dispatch a SQL Warehouse operation."""
    op = operation.lower().strip()
    if op in ("execute_query", "run_query", "query"):
        return execute_sql_query(payload, context, agent, db)
    elif op in ("list_warehouses", "list"):
        return list_sql_warehouses(payload, context, agent, db)
    elif op in ("get_warehouse", "get"):
        return get_sql_warehouse_details(payload, context, agent, db)
    elif op in ("explain_query", "explain"):
        return explain_sql_query(payload, context, agent, db)
    elif op in ("get_query_history", "history"):
        return get_query_history(payload, context, agent, db)
    elif op in ("get_query_result", "result"):
        return get_query_result_by_id(payload, context, agent, db)
    else:
        raise ValueError(
            f"Unsupported sql_warehouse operation: {operation!r}. Supported operations: {SQL_WAREHOUSE_OPERATIONS}"
        )
