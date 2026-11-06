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

def test_connection_raw(
    host: str, port: int, username: str, password: str, database: str
) -> dict:
    import app.data.services.data_catalog_service as svc
    try:
        conn = svc._make_conn(host, port, username, password, database)
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"success": True, "message": "Connection successful", "server_version": version}
    except psycopg2.OperationalError as exc:
        return {"success": False, "message": str(exc), "server_version": None}
    except Exception as exc:
        return {"success": False, "message": f"Unexpected error: {exc}", "server_version": None}
