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

def list_tables(db: Session, conn_id: int, database: str, schema: str) -> list[dict]:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = svc._conn_from_record(record, database)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT t.table_name                          AS name,
                   t.table_schema                        AS schema_name,
                   t.table_type,
                   s.n_live_tup::bigint                  AS row_estimate
            FROM   information_schema.tables t
            LEFT   JOIN pg_stat_user_tables  s
                   ON  s.schemaname = t.table_schema
                   AND s.relname    = t.table_name
            WHERE  t.table_schema = %s
            ORDER  BY t.table_type, t.table_name
            """,
            (schema,),
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()
