"""DuckDB Warehouse Daemon Service.

Exposes a lightweight HTTP/REST query execution interface for containerized
DuckDB SQL warehouses.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("warehouse_daemon")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="CompassX DuckDB Warehouse Daemon", version="1.0.0")

# Active query connection handles for cancellation
_active_connections: dict[str, Any] = {}
_auth_token = os.environ.get("COMPASSX_INTERNAL_SECRET") or os.environ.get("WAREHOUSE_AUTH_TOKEN")
_database_path = os.environ.get("DUCKDB_DATABASE_PATH", ":memory:")


class QueryExecutionRequest(BaseModel):
    query_id: str
    sql: str
    setup_sql: list[str] | None = None
    timeout_sec: int = Field(default=300, ge=1)
    max_threads: int | None = None
    max_memory_mb: int | None = None
    max_rows: int = Field(default=10000, ge=1)
    enable_profiling: bool = True


class ExplainRequest(BaseModel):
    sql: str
    setup_sql: list[str] | None = None


def _verify_auth(secret_header: str | None, auth_header: str | None) -> None:
    if not _auth_token:
        return
    token = secret_header
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
    if token != _auth_token:
        raise HTTPException(status_code=401, detail="Unauthorized warehouse access")


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "engine": "duckdb",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_queries": len(_active_connections),
    }


@app.post("/v1/query")
async def execute_query(
    req: QueryExecutionRequest,
    x_compassx_internal_secret: str | None = Header(None),
    authorization: str | None = Header(None),
):
    _verify_auth(x_compassx_internal_secret, authorization)
    start_time = time.monotonic()

    def _run():
        import duckdb

        conn = duckdb.connect(_database_path)
        _active_connections[req.query_id] = conn
        profile_path = None
        query_analysis = None
        try:
            if req.max_threads:
                conn.execute(f"SET threads TO {int(req.max_threads)}")
            if req.max_memory_mb:
                conn.execute(f"SET memory_limit = '{int(req.max_memory_mb)}MB'")

            for stmt in req.setup_sql or []:
                try:
                    conn.execute(stmt)
                except Exception as stmt_err:
                    logger.warning("Setup statement skipped in query %s: %s (%s)", req.query_id, stmt, stmt_err)

            if req.enable_profiling:
                try:
                    profile_fd, profile_path = tempfile.mkstemp(suffix=".json")
                    os.close(profile_fd)
                    conn.execute("PRAGMA enable_profiling = 'json';")
                    conn.execute(f"PRAGMA profiling_output = '{profile_path}';")
                except Exception:
                    profile_path = None

            rel = conn.execute(req.sql)
            columns = [d[0] for d in (rel.description or [])]
            rows = rel.fetchmany(req.max_rows) if columns else []

            if profile_path:
                try:
                    conn.execute("PRAGMA disable_profiling;")
                    if os.path.exists(profile_path):
                        with open(profile_path, "r", encoding="utf-8") as f:
                            query_analysis = json.load(f)
                except Exception:
                    pass

            return columns, [list(r) for r in rows], query_analysis
        finally:
            _active_connections.pop(req.query_id, None)
            if profile_path and os.path.exists(profile_path):
                try:
                    os.remove(profile_path)
                except Exception:
                    pass
            conn.close()

    try:
        columns, rows, query_analysis = await asyncio.to_thread(_run)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    duration_ms = int((time.monotonic() - start_time) * 1000)
    return {
        "columns": columns,
        "rows": rows,
        "rows_returned": len(rows),
        "bytes_scanned": 0,
        "duration_ms": duration_ms,
        "query_analysis": query_analysis,
    }


@app.post("/v1/cancel/{query_id}")
async def cancel_query(
    query_id: str,
    x_compassx_internal_secret: str | None = Header(None),
    authorization: str | None = Header(None),
):
    _verify_auth(x_compassx_internal_secret, authorization)
    conn = _active_connections.get(query_id)
    if not conn:
        return {"cancelled": False, "message": "Query not found or already completed"}
    try:
        conn.interrupt()
        return {"cancelled": True}
    except Exception as exc:
        return {"cancelled": False, "error": str(exc)}


@app.post("/v1/explain")
async def explain_query(
    req: ExplainRequest,
    x_compassx_internal_secret: str | None = Header(None),
    authorization: str | None = Header(None),
):
    _verify_auth(x_compassx_internal_secret, authorization)

    def _run():
        import duckdb

        conn = duckdb.connect(_database_path)
        try:
            for stmt in req.setup_sql or []:
                try:
                    conn.execute(stmt)
                except Exception as stmt_err:
                    logger.warning("Setup statement skipped in explain: %s (%s)", stmt, stmt_err)
            rows = conn.execute(f"EXPLAIN {req.sql}").fetchall()
            return "\n".join(str(row) for row in rows)
        finally:
            conn.close()

    try:
        explanation = await asyncio.to_thread(_run)
        return {"explanation": explanation}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("services.warehouse_daemon.server:app", host="0.0.0.0", port=port)
