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

def list_databases(db: Session, conn_id: int) -> list[dict]:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = svc._conn_from_record(record)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT datname AS name,
                   pg_catalog.pg_get_userbyid(datdba) AS owner
            FROM   pg_catalog.pg_database
            WHERE  datistemplate = false
            ORDER  BY datname
            """
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()
