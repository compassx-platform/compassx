from __future__ import annotations

import json
import time
from typing import Any

import psycopg2
import psycopg2.extras
from sqlalchemy.orm import Session

from app.models.data_catalog import CatalogConnection
from app.schemas.data_catalog import (
    ColumnInfo,
    ConnectionCreate,
    ConnectionUpdate,
    SqlExecuteResponse,
    TablePreviewResponse,
)

def execute_sql(
    db: Session, conn_id: int, database: str, sql: str, limit: int = 1000
) -> SqlExecuteResponse:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = svc._conn_from_record(record, database)
    start = time.perf_counter()
    try:
        cur = conn.cursor()
        # Wrap in a sub-query to enforce row limit safely
        wrapped = f"SELECT * FROM ({sql.rstrip(';')}) __q LIMIT {limit + 1}"
        cur.execute(wrapped)

        col_names = [desc[0] for desc in cur.description] if cur.description else []
        raw_rows = cur.fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000

        truncated = len(raw_rows) > limit
        rows = [list(svc._serialize_value(v) for v in row) for row in raw_rows[:limit]]

        cur.close()
        conn.rollback()  # ensure read-only behaviour

        return SqlExecuteResponse(
            columns=col_names,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(elapsed_ms, 2),
            truncated=truncated,
        )
    except psycopg2.Error as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        conn.rollback()
        return SqlExecuteResponse(
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=round(elapsed_ms, 2),
            truncated=False,
            error=str(exc).strip(),
        )
    finally:
        conn.close()
