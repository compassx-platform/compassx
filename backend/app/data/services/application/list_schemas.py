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

def list_schemas(db: Session, conn_id: int, database: str) -> list[dict]:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = svc._conn_from_record(record, database)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT schema_name AS name,
                   schema_owner AS owner
            FROM   information_schema.schemata
            WHERE  schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND  schema_name NOT LIKE 'pg_temp_%'
              AND  schema_name NOT LIKE 'pg_toast_temp_%'
            ORDER  BY schema_name
            """
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()
