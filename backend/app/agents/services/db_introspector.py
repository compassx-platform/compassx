"""Dynamic DB connection builder and schema introspector.

Supports: PostgreSQL, MySQL, MS SQL Server, SQLite, Snowflake, BigQuery, Databricks.
Credentials are decrypted on the fly — never stored in plain text.

Usage:
    from app.services.db_introspector import build_engine, get_schema

    engine = build_engine(db_conn_row)
    schema = get_schema(engine)          # {"table_name": ["col1", "col2"], ...}
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.models.agents import DBConnection, DBType
from app.services.encryption import decrypt_field

logger = logging.getLogger(__name__)


def build_engine(conn: DBConnection) -> Engine:
    """Build a SQLAlchemy engine for the given DB connection row."""
    username = decrypt_field(conn.username_enc) if conn.username_enc else ""
    password = decrypt_field(conn.password_enc) if conn.password_enc else ""
    host = conn.host or "localhost"
    port = conn.port
    db_name = conn.db_name or ""
    ssl = conn.ssl_config or {}

    match conn.db_type:
        case DBType.postgres:
            url = f"postgresql+psycopg2://{username}:{password}@{host}:{port or 5432}/{db_name}"
        case DBType.mysql:
            url = f"mysql+pymysql://{username}:{password}@{host}:{port or 3306}/{db_name}"
        case DBType.mssql:
            url = f"mssql+pyodbc://{username}:{password}@{host}:{port or 1433}/{db_name}?driver=ODBC+Driver+17+for+SQL+Server"
        case DBType.sqlite:
            url = f"sqlite:///{db_name}"
        case DBType.snowflake:
            account = ssl.get("account", "")
            warehouse = ssl.get("warehouse", "")
            url = f"snowflake://{username}:{password}@{account}/{db_name}?warehouse={warehouse}"
        case DBType.bigquery:
            project = ssl.get("project", db_name)
            url = f"bigquery://{project}"
        case DBType.databricks:
            http_path = ssl.get("http_path", "")
            url = f"databricks://token:{password}@{host}?http_path={http_path}&catalog={db_name}"
        case DBType.oracle:
            url = f"oracle+cx_oracle://{username}:{password}@{host}:{port or 1521}/{db_name}"
        case _:
            raise ValueError(f"Unsupported db_type: {conn.db_type}")

    connect_args: dict[str, Any] = {}
    if ssl.get("ssl_required") and conn.db_type == DBType.postgres:
        connect_args["sslmode"] = "require"

    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def get_schema(engine: Engine) -> dict[str, list[str]]:
    """Return {table_name: [column_names]} for all user tables in the DB."""
    inspector = inspect(engine)
    result = {}
    try:
        schemas = inspector.get_schema_names()
    except Exception:
        schemas = [None]

    for schema in schemas:
        if schema in ("information_schema", "pg_catalog", "sys"):
            continue
        try:
            for table in inspector.get_table_names(schema=schema):
                qualified = f"{schema}.{table}" if schema and schema != "public" else table
                cols = [c["name"] for c in inspector.get_columns(table, schema=schema)]
                result[qualified] = cols
        except Exception as exc:
            logger.warning("Schema introspection failed for schema %s: %s", schema, exc)

    return result


def test_connection(conn: DBConnection) -> tuple[bool, str]:
    """Try to connect and run a trivial query. Returns (success, message)."""
    try:
        engine = build_engine(conn)
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)
