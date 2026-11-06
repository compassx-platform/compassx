from __future__ import annotations

import json
from typing import Any

import httpx
import psycopg2
import psycopg2.extras
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.catalog.models import (
    CatalogTableType,
    UnifiedCatalog,
    UnifiedCatalogColumn,
    UnifiedCatalogLineage,
    UnifiedCatalogSchema,
    UnifiedCatalogTable,
    UnifiedCatalogNotebook,
    UnifiedCatalogDashboard,
    UnifiedCatalogQuery,
    UnifiedCatalogQueryVersion,
    UnifiedCatalogConnection,
)
from app.models.agents import DBConnection
from app.catalog.schemas import (
    CatalogColumnRead,
    CatalogSchemaSummary,
    CatalogSummary,
    CatalogTableRead,
    LineageEdgeCreate,
    LineageEdgeRead,
    LineageGraphRead,
    RemoteDatabaseRead,
    RemoteSchemaRead,
    RemoteTableRead,
    SampleDataRead,
    SchemaCreate,
    TableCreate,
    DashboardCreate,
    DashboardRead,
    DashboardUpdate,
    DashboardMove,
    VolumeCreate,
    NotebookCreate,
    NotebookUpdate,
    NotebookMove,
    QueryCreate,
    QueryRead,
    QueryUpdate,
    QueryMove,
    QueryVersionRead,
    QueryCreateVersion,
)
from app.services.encryption import decrypt_field, encrypt_field
from app.catalog.storage_context import resolve_catalog_storage, resolve_catalog_storage_by_schema_id

def _get_connection(db: Session, connection_id: Any) -> Any:
    if not connection_id:
        raise ValueError("Connection not found")
    from app.database import AccountSessionLocal
    sys_db = AccountSessionLocal()
    try:
        # 1. Check DBConnection by integer ID if int or digit string
        if isinstance(connection_id, int) or (isinstance(connection_id, str) and connection_id.isdigit()):
            record = sys_db.query(DBConnection).filter(DBConnection.id == int(connection_id)).first()
            if record:
                sys_db.expunge(record)
                return record

        # 2. Check UnifiedCatalogConnection (External Connection) by UUID or name
        cat_conn = sys_db.query(UnifiedCatalogConnection).filter(
            or_(
                UnifiedCatalogConnection.id == str(connection_id),
                UnifiedCatalogConnection.name == str(connection_id),
            )
        ).first()
        if cat_conn:
            sys_db.expunge(cat_conn)
            return cat_conn

        # 3. Fallback: check DBConnection by name or str(id)
        record = sys_db.query(DBConnection).filter(
            or_(
                DBConnection.id == connection_id if isinstance(connection_id, int) else False,
                DBConnection.name == str(connection_id),
            )
        ).first()
        if record:
            sys_db.expunge(record)
            return record

        raise ValueError(f"Connection '{connection_id}' not found")
    finally:
        sys_db.close()

def _get_connection_name(db: Session, connection_id: Any) -> str | None:
    if not connection_id:
        return None
    try:
        conn = _get_connection(db, connection_id)
        return conn.name if conn else None
    except Exception:
        return None

def _connect_record(record: Any, database: str | None=None):
    if isinstance(record, UnifiedCatalogConnection):
        config = record.config or {}
        decrypted_password = ""
        decrypted_username = config.get("username") or config.get("user") or ""
        if record.auth_config:
            try:
                decrypted_raw = decrypt_field(record.auth_config)
                if decrypted_raw:
                    try:
                        auth_json = json.loads(decrypted_raw)
                        if isinstance(auth_json, dict):
                            decrypted_password = auth_json.get("password") or auth_json.get("secret") or auth_json.get("pass") or decrypted_raw
                            if not decrypted_username and auth_json.get("username"):
                                decrypted_username = auth_json.get("username")
                        else:
                            decrypted_password = str(auth_json)
                    except Exception:
                        decrypted_password = decrypted_raw
            except Exception as exc:
                import logging
                logging.getLogger("app.catalog.service").warning("Could not decrypt auth_config for connection %s: %s", record.name, exc)

        ssl_mode = "require" if (config.get("ssl_required") or config.get("ssl")) else "prefer"
        return _connect_raw(
            host=config.get("host") or "localhost",
            port=int(config.get("port") or 5432),
            database=database or config.get("database") or config.get("db_name") or "postgres",
            username=decrypted_username,
            password=decrypted_password,
            ssl_mode=ssl_mode,
        )

    ssl_mode = "require" if (record.ssl_config and record.ssl_config.get("ssl_required")) else "prefer"
    return _connect_raw(
        host=record.host or "localhost",
        port=record.port or 5432,
        database=database or record.db_name or "postgres",
        username=decrypt_field(record.username_enc) if record.username_enc else "",
        password=decrypt_field(record.password_enc) if record.password_enc else "",
        ssl_mode=ssl_mode,
    )

def _connect_raw(*, host: str, port: int, database: str, username: str, password: str, ssl_mode: str):
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=username,
        password=password,
        sslmode=ssl_mode,
        connect_timeout=10,
        options="-c statement_timeout=30000",
    )

