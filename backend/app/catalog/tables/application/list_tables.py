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

class ListTables:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog: str | None=None, schema_name: str | None=None) -> list[CatalogTableRead]:
        from app.catalog.runtime import _to_table_read, browse_connection_tables, _get_connection_name
        if catalog:
            cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog).first()
            if cat_model and cat_model.catalog_type == "postgres" and cat_model.connection_id and cat_model.database_name:
                if not schema_name:
                    return []
                try:
                    # Query remote tables dynamically
                    remote_tables = browse_connection_tables(db, cat_model.connection_id, cat_model.database_name, schema_name)
                    result = []
                    for tbl in remote_tables:
                        fqn = f"{catalog}.{schema_name}.{tbl.name}"
                        result.append(
                            CatalogTableRead(
                                id=fqn,
                                fqn=fqn,
                                catalog=catalog,
                                schema_name=schema_name,
                                name=tbl.name,
                                table_type=CatalogTableType.POSTGRES_NATIVE,
                                description=f"Dynamically loaded Postgres Table: {tbl.name}",
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
                                pg_table=tbl.name,
                                columns=[]
                            )
                        )
                    return result
                except Exception as e:
                    print(f"Error listing dynamic tables: {e}")
                    return []

        query = (
            db.query(UnifiedCatalogTable)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
            .options(joinedload(UnifiedCatalogTable.columns), joinedload(UnifiedCatalogTable.connection), joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog))
            .order_by(UnifiedCatalog.name, UnifiedCatalogSchema.name, UnifiedCatalogTable.name)
        )
        if catalog:
            query = query.filter(UnifiedCatalog.name == catalog)
        if schema_name:
            query = query.filter(UnifiedCatalogSchema.name == schema_name)
        return [_to_table_read(item) for item in query.all()]

def list_tables(db: Session, catalog: str | None=None, schema_name: str | None=None) -> list[CatalogTableRead]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = ListTables(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog, schema_name)
