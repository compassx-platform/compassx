"""Data Catalog service – manages connections and introspects PostgreSQL databases."""

from __future__ import annotations

import logging
import time
from typing import Any

import json

import psycopg2
import psycopg2.extras
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings
from app.models.data_catalog import CatalogConnection
from app.schemas.data_catalog import (
    ConnectionCreate,
    ConnectionUpdate,
    ColumnInfo,
    TablePreviewResponse,
    SqlExecuteResponse,
)

logger = logging.getLogger(__name__)

# ── Encryption helpers ────────────────────────────────────────────────────────

def _fernet() -> Fernet:
    return Fernet(settings.catalog_fernet_key)


def encrypt_password(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_password(cipher: str) -> str:
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except (InvalidToken, Exception) as exc:
        logger.error("Failed to decrypt connection password: %s", exc)
        raise ValueError("Cannot decrypt stored password – check CATALOG_ENCRYPTION_KEY") from exc


# ── Connection helpers ────────────────────────────────────────────────────────

def _make_conn(host: str, port: int, user: str, password: str, database: str):
    """Open a psycopg2 connection with a short timeout."""
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=database,
        connect_timeout=10,
        options="-c statement_timeout=30000",  # 30 s query timeout
    )


def _conn_from_record(record: CatalogConnection, database: str | None = None):
    password = decrypt_password(record.password_enc)
    db = database or record.default_database
    return _make_conn(record.host, record.port, record.username, password, db)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_connections(db: Session) -> list[CatalogConnection]:
    from app.data.services.application.list_connections import list_connections as list_connections_action
    return list_connections_action(db=db)


def get_connection(db: Session, conn_id: int) -> CatalogConnection | None:
    from app.data.services.application.get_connection import get_connection as get_connection_action
    return get_connection_action(db=db, conn_id=conn_id)


def create_connection(db: Session, data: ConnectionCreate) -> CatalogConnection:
    from app.data.services.application.create_connection import create_connection as create_connection_action
    return create_connection_action(db=db, data=data)


def update_connection(db: Session, conn_id: int, data: ConnectionUpdate) -> CatalogConnection | None:
    from app.data.services.application.update_connection import update_connection as update_connection_action
    return update_connection_action(db=db, conn_id=conn_id, data=data)


def delete_connection(db: Session, conn_id: int) -> bool:
    from app.data.services.application.delete_connection import delete_connection as delete_connection_action
    return delete_connection_action(db=db, conn_id=conn_id)


# ── Connection test ───────────────────────────────────────────────────────────

def test_connection_raw(
    host: str, port: int, username: str, password: str, database: str
) -> dict:
    from app.data.services.application.test_connection_raw import test_connection_raw as test_connection_raw_action
    return test_connection_raw_action(host=host, port=port, username=username, password=password, database=database)


# ── Catalog browsing ──────────────────────────────────────────────────────────

def list_databases(db: Session, conn_id: int) -> list[dict]:
    from app.data.services.application.list_databases import list_databases as list_databases_action
    return list_databases_action(db=db, conn_id=conn_id)


def list_schemas(db: Session, conn_id: int, database: str) -> list[dict]:
    from app.data.services.application.list_schemas import list_schemas as list_schemas_action
    return list_schemas_action(db=db, conn_id=conn_id, database=database)


def list_tables(db: Session, conn_id: int, database: str, schema: str) -> list[dict]:
    from app.data.services.application.list_tables import list_tables as list_tables_action
    return list_tables_action(db=db, conn_id=conn_id, database=database, schema=schema)


def get_table_preview(
    db: Session, conn_id: int, database: str, schema: str, table: str, limit: int = 100
) -> TablePreviewResponse:
    from app.data.services.application.get_table_preview import get_table_preview as get_table_preview_action
    return get_table_preview_action(db=db, conn_id=conn_id, database=database, schema=schema, table=table, limit=limit)


# ── SQL execution ─────────────────────────────────────────────────────────────

def execute_sql(
    db: Session, conn_id: int, database: str, sql: str, limit: int = 1000
) -> SqlExecuteResponse:
    from app.data.services.application.execute_sql import execute_sql as execute_sql_action
    return execute_sql_action(db=db, conn_id=conn_id, database=database, sql=sql, limit=limit)


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _serialize_value(v: Any) -> Any:
    """Convert non-JSON-serialisable types to strings.

    dict/list (JSON/JSONB columns) are serialised with json.dumps so the
    frontend receives a valid JSON string rather than Python's repr.
    """
    if v is None:
        return None
    if isinstance(v, (int, float, bool, str)):
        return v
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str)
    return str(v)


def _serialize_row(row: dict) -> dict:
    return {k: _serialize_value(v) for k, v in row.items()}