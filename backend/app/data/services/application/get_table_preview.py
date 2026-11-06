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

def get_table_preview(
    db: Session, conn_id: int, database: str, schema: str, table: str, limit: int = 100
) -> TablePreviewResponse:
    import app.data.services.data_catalog_service as svc
    record = svc.get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = svc._conn_from_record(record, database)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Column metadata
        cur.execute(
            """
            SELECT column_name,
                   data_type,
                   is_nullable,
                   column_default,
                   ordinal_position,
                   character_maximum_length
            FROM   information_schema.columns
            WHERE  table_schema = %s
              AND  table_name   = %s
            ORDER  BY ordinal_position
            """,
            (schema, table),
        )
        col_rows = cur.fetchall()
        columns = [
            ColumnInfo(
                name=r["column_name"],
                data_type=r["data_type"],
                is_nullable=(r["is_nullable"] == "YES"),
                column_default=r["column_default"],
                ordinal_position=r["ordinal_position"],
                character_maximum_length=r["character_maximum_length"],
            )
            for r in col_rows
        ]

        # Row count estimate
        cur.execute(
            "SELECT reltuples::bigint FROM pg_class WHERE relname = %s", (table,)
        )
        count_row = cur.fetchone()
        total_rows = int(count_row["reltuples"]) if count_row else 0

        # Sample data
        safe_schema = schema.replace('"', '""')
        safe_table = table.replace('"', '""')
        cur.execute(f'SELECT * FROM "{safe_schema}"."{safe_table}" LIMIT %s', (limit,))
        data_rows = cur.fetchall()

        rows = [svc._serialize_row(dict(r)) for r in data_rows]
        cur.close()

        return TablePreviewResponse(
            columns=columns,
            rows=rows,
            total_rows=total_rows,
            truncated=len(rows) >= limit,
        )
    finally:
        conn.close()
