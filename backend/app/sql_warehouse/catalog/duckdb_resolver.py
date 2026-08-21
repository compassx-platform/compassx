"""
duckdb_resolver.py — Builds the DuckDB session setup SQL plan.

Postgres catalogs are attached through DuckDB's postgres extension. Iceberg
tables are exposed through iceberg_scan(), which resolves the active snapshot
and delegates data-file reads to DuckDB's native Parquet scanner. This retains
Iceberg correctness and Parquet projection/predicate pushdown.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload
from app.database import AccountSessionLocal

from app.agents.models.agents import DBConnection
from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema
from app.services.encryption import decrypt_field
from app.storage.db_models import StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class DuckDBCatalogPlan:
    """SQL statements to run at the start of every DuckDB session."""
    setup_sql: list[str]


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _pg_attach_string(connection: DBConnection, database: str | None) -> str:
    username = decrypt_field(connection.username_enc) if connection.username_enc else ""
    password = decrypt_field(connection.password_enc) if connection.password_enc else ""
    parts = {
        "host": connection.host or "localhost",
        "port": str(connection.port or 5432),
        "dbname": database or connection.db_name or "postgres",
        "user": username,
        "password": password,
    }
    if connection.ssl_config and connection.ssl_config.get("ssl_required"):
        parts["sslmode"] = "require"
    return " ".join(f"{key}={value}" for key, value in parts.items())


def _build_secret_setup(provider: str, secret_id: str, config: dict) -> list[str]:
    secret_name = _quote_ident("compassx_" + secret_id.replace("-", "_"))
    if provider in {"s3", "minio"}:
        key = config.get("access_key") or ""
        secret = config.get("secret_key") or ""
        bucket = config.get("bucket") or ""
        region = config.get("region") or "us-east-1"
        options = [
            "TYPE s3",
            f"KEY_ID {_quote_literal(key)}",
            f"SECRET {_quote_literal(secret)}",
            f"REGION {_quote_literal(region)}"
        ]
        endpoint = config.get("endpoint") or ""
        if endpoint:
            endpoint = endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
            options += [
                f"ENDPOINT {_quote_literal(endpoint)}",
                "URL_STYLE 'path'",
                f"USE_SSL {'true' if (config.get('endpoint') or '').startswith('https://') else 'false'}"
            ]
        return ["INSTALL httpfs", "LOAD httpfs", f"CREATE OR REPLACE SECRET {secret_name} ({', '.join(options)})"]
    if provider == "azure":
        account_name = config.get("account_name") or ""
        account_key = config.get("account_key") or ""
        connection = f"AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
        return [
            "INSTALL azure",
            "LOAD azure",
            "SET azure_transport_option_type = 'curl'",
            f"CREATE OR REPLACE SECRET {secret_name} (TYPE azure, CONNECTION_STRING {_quote_literal(connection)})",
        ]
    raise ValueError(f"Unsupported storage provider '{provider}'")


def _metadata_uri_from_config(provider: str, config: dict, metadata_location: str) -> str:
    if "://" in metadata_location:
        return metadata_location
    path = metadata_location.strip("/")
    if provider == "azure":
        container = config.get("container") or ""
        return f"az://{container}/{path}"
    bucket = config.get("bucket") or ""
    return f"s3://{bucket}/{path}"


def _data_file_uri_from_config(provider: str, config: dict, storage_location: str, filename: str) -> str:
    path = f"{storage_location.strip('/')}/data/{filename.lstrip('/')}"
    if provider == "azure":
        container = config.get("container") or ""
        return f"az://{container}/{path}"
    bucket = config.get("bucket") or ""
    return f"s3://{bucket}/{path}"


def _resolve_duckdb_storage_config(db: Session, catalog: UnifiedCatalog, schema: UnifiedCatalogSchema) -> tuple[str, str, dict] | None:
    from app.storage.db_models import StorageBackend
    from app.services.encryption import decrypt_field

    backend_id = schema.storage_backend_id or catalog.storage_backend_id
    if backend_id:
        backend = db.query(StorageBackend).filter(StorageBackend.id == backend_id).first()
        if backend:
            config = {
                "access_key": decrypt_field(backend.encrypted_access_key) if backend.encrypted_access_key else "",
                "secret_key": decrypt_field(backend.encrypted_secret_key) if backend.encrypted_secret_key else "",
                "bucket": backend.s3_bucket or "",
                "region": backend.s3_region or "us-east-1",
                "endpoint": backend.s3_endpoint_url or "",
                "account_name": backend.azure_account_name or "",
                "account_key": decrypt_field(backend.encrypted_azure_account_key) if backend.encrypted_azure_account_key else "",
                "container": backend.azure_container or "",
            }
            return backend.provider, backend.id, config

    # Fall back to workspace level storage
    from app.workspace.models import Workspace
    from app.workspace.storage_resolver import resolve_workspace_storage

    workspace = db.query(Workspace).filter(Workspace.status == "active").first()
    if workspace:
        provider, config = resolve_workspace_storage(workspace)
        return provider, workspace.id, config

    return None


def _file_scan_sql(uri: str, filename: str, file_format: str | None) -> str:
    """Return the native DuckDB scanner matching an app-managed data file."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    fmt = suffix or (file_format or "").lower()
    quoted_uri = _quote_literal(uri)
    if fmt == "parquet":
        return f"read_parquet({quoted_uri}, union_by_name = true)"
    if fmt in {"csv", "tsv"}:
        delimiter = "," if fmt == "csv" else "\\t"
        return f"read_csv_auto({quoted_uri}, header = true, delim = {_quote_literal(delimiter)})"
    if fmt in {"json", "jsonl", "ndjson"}:
        return f"read_json_auto({quoted_uri})"
    raise ValueError(
        f"DuckDB cannot directly scan data file '{filename}' (format '{fmt or 'unknown'}'). "
        "Convert the table data to Parquet, CSV, or JSON."
    )


def build_duckdb_catalog_plan(db: Session) -> DuckDBCatalogPlan:
    """
    Build the list of DuckDB SQL statements needed before executing a user query.

    No table data is downloaded or materialized here. Keeping iceberg_scan in
    the view lets DuckDB optimize the user's filters and selected columns into
    its Parquet scans.
    """
    setup: list[str] = []
    import os, certifi
    ca_cert_path = certifi.where() if os.path.exists(certifi.where()) else "/etc/ssl/certs/ca-certificates.crt"
    if os.path.exists(ca_cert_path):
        setup.append(f"SET ca_cert_file = {_quote_literal(ca_cert_path)}")

    configured_backends: set[str] = set()
    iceberg_loaded = False

    sys_db = AccountSessionLocal()
    try:
        connections = sys_db.query(DBConnection).all()
        conn_map = {c.id: c for c in connections}

        catalogs = (
            sys_db.query(UnifiedCatalog)
            .options(
                joinedload(UnifiedCatalog.schemas).joinedload(UnifiedCatalogSchema.tables),
            )
            .order_by(UnifiedCatalog.name)
            .all()
        )

        RESERVED_DUCKDB_DATABASES = {"main", "temp", "system", "memory"}

        for catalog in catalogs:
            is_reserved = catalog.name.lower() in RESERVED_DUCKDB_DATABASES

            if (
                catalog.catalog_type == "postgres"
                and catalog.connection_id
                and catalog.database_name
                and conn_map.get(catalog.connection_id)
            ):
                if not is_reserved:
                    setup.extend([
                        "INSTALL postgres",
                        "LOAD postgres",
                        f"ATTACH IF NOT EXISTS {_quote_literal(_pg_attach_string(conn_map.get(catalog.connection_id), catalog.database_name))} "
                        f"AS {_quote_ident(catalog.name)} (TYPE postgres)",
                    ])
                continue

            if not is_reserved:
                setup.append(f"ATTACH IF NOT EXISTS ':memory:' AS {_quote_ident(catalog.name)}")

            for schema in catalog.schemas:
                if not is_reserved:
                    setup.append(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(catalog.name)}.{_quote_ident(schema.name)}")
                else:
                    setup.append(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema.name)}")
                
                storage_cfg = _resolve_duckdb_storage_config(sys_db, catalog, schema)
                if not storage_cfg:
                    continue
                provider, secret_id, config = storage_cfg
                
                if secret_id not in configured_backends:
                    setup.extend(_build_secret_setup(provider, secret_id, config))
                    configured_backends.add(secret_id)
                if not iceberg_loaded:
                    setup.extend(["INSTALL iceberg", "LOAD iceberg"])
                    iceberg_loaded = True

                for table in schema.tables:
                    table_type = table.table_type.value if hasattr(table.table_type, "value") else table.table_type
                    if table_type != "iceberg":
                        continue
                    data_file = (table.properties or {}).get("data_file")
                    if data_file and table.storage_location:
                        # Tables uploaded through CompassX currently have metadata
                        # without an Iceberg snapshot/manifest. Scan their one
                        # registered Parquet file directly so DuckDB can push
                        # filters and projections into PARQUET_SCAN.
                        source = _file_scan_sql(
                            _data_file_uri_from_config(provider, config, table.storage_location, data_file),
                            data_file,
                            table.file_format,
                        )
                    elif table.metadata_location:
                        # Externally managed tables have real Iceberg snapshots;
                        # iceberg_scan selects the valid files and then delegates
                        # their reads to DuckDB's Parquet execution path.
                        source = f"iceberg_scan({_quote_literal(_metadata_uri_from_config(provider, config, table.metadata_location))})"
                    else:
                        logger.warning("Iceberg table %s has neither a data file nor metadata location", table.name)
                        continue
                    
                    if not is_reserved:
                        setup.append(
                            f"CREATE OR REPLACE VIEW {_quote_ident(catalog.name)}.{_quote_ident(schema.name)}.{_quote_ident(table.name)} AS "
                            f"SELECT * FROM {source}"
                        )
                    else:
                        setup.append(
                            f"CREATE OR REPLACE VIEW {_quote_ident(schema.name)}.{_quote_ident(table.name)} AS "
                            f"SELECT * FROM {source}"
                        )
    finally:
        sys_db.close()

    return DuckDBCatalogPlan(setup_sql=setup)
