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

class GetTable:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, fqn: str) -> CatalogTableRead:
        from app.catalog.runtime import _parse_fqn, _to_table_read, introspect_columns, _get_connection_name
        catalog_name, schema_name, table_name = _parse_fqn(fqn)
        cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()

        # For postgres catalogs: prefer stored synced rows; fall back to live introspection
        if cat_model and cat_model.catalog_type == "postgres" and cat_model.connection_id and cat_model.database_name:
            stored = (
                db.query(UnifiedCatalogTable)
                .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
                .options(joinedload(UnifiedCatalogTable.columns), joinedload(UnifiedCatalogTable.connection), joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
                .filter(
                    UnifiedCatalogSchema.catalog_id == cat_model.id,
                    UnifiedCatalogSchema.name == schema_name,
                    UnifiedCatalogTable.name == table_name,
                )
                .first()
            )
            if stored and stored.columns:
                return _to_table_read(stored)

            # Fall back to live introspection (not yet synced)
            temp_table = UnifiedCatalogTable(
                table_type=CatalogTableType.POSTGRES_NATIVE,
                connection_id=cat_model.connection_id,
                source_database=cat_model.database_name,
                pg_schema=schema_name,
                pg_table=table_name,
            )
            try:
                columns = introspect_columns(db, temp_table)
                return CatalogTableRead(
                    id=fqn,
                    fqn=fqn,
                    catalog=catalog_name,
                    schema_name=schema_name,
                    name=table_name,
                    table_type=CatalogTableType.POSTGRES_NATIVE,
                    description=f"Dynamically loaded Postgres Table: {table_name}",
                    owner="postgres-owner",
                    read_roles=[],
                    write_roles=[],
                    properties={},
                    created_at=cat_model.created_at,
                    updated_at=cat_model.created_at,
                    connection_id=cat_model.connection_id,
                    connection_name=cat_model.connection.name if cat_model.connection else _get_connection_name(db, cat_model.connection_id),
                    source_database=cat_model.database_name,
                    pg_schema=schema_name,
                    pg_table=table_name,
                    columns=columns
                )
            except Exception as e:
                raise ValueError(f"Failed to introspect table {fqn}: {e}")

        table = (
            db.query(UnifiedCatalogTable)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
            .options(joinedload(UnifiedCatalogTable.columns), joinedload(UnifiedCatalogTable.connection), joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
            .filter(
                UnifiedCatalog.name == catalog_name,
                UnifiedCatalogSchema.name == schema_name,
                UnifiedCatalogTable.name == table_name,
            )
            .first()
        )
        if not table:
            raise ValueError(f"Table '{fqn}' not found")
        return _to_table_read(table)

def get_table(db: Session, fqn: str) -> CatalogTableRead:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = GetTable(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, fqn)
