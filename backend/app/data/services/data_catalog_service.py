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
    return db.query(CatalogConnection).order_by(CatalogConnection.created_at).all()


def get_connection(db: Session, conn_id: int) -> CatalogConnection | None:
    return db.query(CatalogConnection).filter(CatalogConnection.id == conn_id).first()


def create_connection(db: Session, data: ConnectionCreate) -> CatalogConnection:
    record = CatalogConnection(
        name=data.name,
        host=data.host,
        port=data.port,
        username=data.username,
        password_enc=encrypt_password(data.password),
        default_database=data.default_database,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_connection(db: Session, conn_id: int, data: ConnectionUpdate) -> CatalogConnection | None:
    record = get_connection(db, conn_id)
    if not record:
        return None
    if data.name is not None:
        record.name = data.name
    if data.host is not None:
        record.host = data.host
    if data.port is not None:
        record.port = data.port
    if data.username is not None:
        record.username = data.username
    if data.password is not None:
        record.password_enc = encrypt_password(data.password)
    if data.default_database is not None:
        record.default_database = data.default_database
    db.commit()
    db.refresh(record)
    return record


def delete_connection(db: Session, conn_id: int) -> bool:
    record = get_connection(db, conn_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


# ── Connection test ───────────────────────────────────────────────────────────

def test_connection_raw(
    host: str, port: int, username: str, password: str, database: str
) -> dict:
    try:
        conn = _make_conn(host, port, username, password, database)
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


# ── Catalog browsing ──────────────────────────────────────────────────────────

def list_databases(db: Session, conn_id: int) -> list[dict]:
    record = get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = _conn_from_record(record)
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


def list_schemas(db: Session, conn_id: int, database: str) -> list[dict]:
    record = get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = _conn_from_record(record, database)
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


def list_tables(db: Session, conn_id: int, database: str, schema: str) -> list[dict]:
    record = get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = _conn_from_record(record, database)
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


def get_table_preview(
    db: Session, conn_id: int, database: str, schema: str, table: str, limit: int = 100
) -> TablePreviewResponse:
    record = get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = _conn_from_record(record, database)
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

        rows = [_serialize_row(dict(r)) for r in data_rows]
        cur.close()

        return TablePreviewResponse(
            columns=columns,
            rows=rows,
            total_rows=total_rows,
            truncated=len(rows) >= limit,
        )
    finally:
        conn.close()


# ── SQL execution ─────────────────────────────────────────────────────────────

def execute_sql(
    db: Session, conn_id: int, database: str, sql: str, limit: int = 1000
) -> SqlExecuteResponse:
    record = get_connection(db, conn_id)
    if not record:
        raise ValueError(f"Connection {conn_id} not found")

    conn = _conn_from_record(record, database)
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
        rows = [list(_serialize_value(v) for v in row) for row in raw_rows[:limit]]

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