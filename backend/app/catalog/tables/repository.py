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

def introspect_columns(db: Session, table: UnifiedCatalogTable) -> list[CatalogColumnRead]:
    from app.catalog.runtime import _get_connection, _connect_record
    if table.table_type == CatalogTableType.POSTGRES_NATIVE:
        connection = _get_connection(db, table.connection_id)
        conn = _connect_record(connection, table.source_database)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table.pg_schema, table.pg_table),
            )
            rows = cur.fetchall()
            return [
                CatalogColumnRead(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    nullable=row["is_nullable"] == "YES",
                    ordinal=row["ordinal_position"],
                )
                for row in rows
            ]
        finally:
            conn.close()
    return _introspect_iceberg_columns(table.metadata_location)

def _introspect_iceberg_columns(metadata_location: str | None) -> list[CatalogColumnRead]:
    if not metadata_location:
        return []
    if metadata_location.startswith("http://") or metadata_location.startswith("https://"):
        with httpx.Client(timeout=10) as client:
            resp = client.get(metadata_location)
            resp.raise_for_status()
            metadata = resp.json()
    else:
        return []

    current_schema_id = metadata.get("current-schema-id", 0)
    schemas = metadata.get("schemas") or ([metadata.get("schema")] if metadata.get("schema") else [])
    current_schema = next((s for s in schemas if s and s.get("schema-id") == current_schema_id), schemas[0] if schemas else {})
    fields = current_schema.get("fields", []) if current_schema else []
    return [
        CatalogColumnRead(
            name=field["name"],
            data_type=_resolve_iceberg_type(field.get("type")),
            nullable=not field.get("required", False),
            description=field.get("doc"),
            ordinal=index + 1,
        )
        for index, field in enumerate(fields)
    ]

def _resolve_iceberg_type(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        kind = value.get("type", "unknown")
        if kind == "list":
            return f"list<{_resolve_iceberg_type(value.get('element-type', 'string'))}>"
        if kind == "map":
            return f"map<{_resolve_iceberg_type(value.get('key-type', 'string'))},{_resolve_iceberg_type(value.get('value-type', 'string'))}>"
        if kind == "decimal":
            return f"decimal({value.get('precision', 38)},{value.get('scale', 0)})"
        return kind
    return "unknown"

def _replace_columns(db: Session, table: UnifiedCatalogTable, columns: list[CatalogColumnRead]) -> None:
    db.query(UnifiedCatalogColumn).filter(UnifiedCatalogColumn.table_id == table.id).delete()
    for column in columns:
        db.add(
            UnifiedCatalogColumn(
                table_id=table.id,
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                description=column.description,
                ordinal=column.ordinal,
                properties=column.properties,
            )
        )
    db.commit()

def _to_table_read(table: UnifiedCatalogTable) -> CatalogTableRead:
    catalog = table.schema.catalog
    fqn = f"{catalog.name}.{table.schema.name}.{table.name}"
    return CatalogTableRead(
        id=table.id,
        fqn=fqn,
        catalog=catalog.name,
        schema_name=table.schema.name,
        name=table.name,
        table_type=table.table_type,
        description=table.description,
        owner=table.owner,
        read_roles=list(table.read_roles or []),
        write_roles=list(table.write_roles or []),
        properties=dict(table.properties or {}),
        created_at=table.created_at,
        updated_at=table.updated_at,
        connection_id=table.connection_id,
        connection_name=table.connection.name if table.connection else None,
        source_database=table.source_database,
        pg_schema=table.pg_schema,
        pg_table=table.pg_table,
        metadata_location=table.metadata_location,
        storage_location=table.storage_location,
        columns=[
            CatalogColumnRead(
                name=column.name,
                data_type=column.data_type,
                nullable=column.nullable,
                description=column.description,
                ordinal=column.ordinal,
                properties=dict(column.properties or {}),
            )
            for column in sorted(table.columns, key=lambda item: item.ordinal)
        ],
    )

def _parse_fqn(fqn: str) -> tuple[str, str, str]:
    parts = fqn.split(".")
    if len(parts) != 3:
        raise ValueError(f"Expected catalog.schema.table, got '{fqn}'")
    return parts[0], parts[1], parts[2]

def _get_table_model(db: Session, fqn: str) -> UnifiedCatalogTable:
    catalog_name, schema_name, table_name = _parse_fqn(fqn)
    row = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .options(joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
        .filter(
            UnifiedCatalog.name == catalog_name,
            UnifiedCatalogSchema.name == schema_name,
            UnifiedCatalogTable.name == table_name,
        )
        .first()
    )
    if not row:
        raise ValueError(f"Table '{fqn}' not found")
    return row

