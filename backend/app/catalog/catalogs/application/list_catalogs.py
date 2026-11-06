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

class ListCatalogs:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, workspace_id: str | None=None) -> list[CatalogSummary]:
        from app.catalog.runtime import ensure_default_catalog, browse_connection_schemas
        ensure_default_catalog(db)
        query = (
            db.query(UnifiedCatalog)
            .options(joinedload(UnifiedCatalog.schemas).joinedload(UnifiedCatalogSchema.tables))
            .order_by(UnifiedCatalog.name)
        )
        if workspace_id:
            from app.catalog.models import CatalogWorkspaceBinding
            query = query.outerjoin(CatalogWorkspaceBinding).filter(
                (UnifiedCatalog.all_workspaces == True) |
                (CatalogWorkspaceBinding.workspace_id == workspace_id)
            )
        catalogs = query.all()
        result: list[CatalogSummary] = []
        for catalog in catalogs:
            if catalog.catalog_type == "postgres" and catalog.connection_id and catalog.database_name:
                try:
                    # Query schemas from the connection dynamically
                    remote_schemas = browse_connection_schemas(db, catalog.connection_id, catalog.database_name)
                    schema_summaries = [
                        CatalogSchemaSummary(
                            id=f"dynamic-{catalog.name}-{sch.name}",
                            name=sch.name,
                            description=f"Remote Postgres Schema: {sch.name}",
                            table_count=0,
                        )
                        for sch in remote_schemas
                    ]
                    result.append(
                        CatalogSummary(
                            id=catalog.id,
                            name=catalog.name,
                            description=catalog.description,
                            catalog_type=catalog.catalog_type,
                            connection_id=catalog.connection_id,
                            database_name=catalog.database_name,
                            schema_count=len(schema_summaries),
                            table_count=0,
                            schemas=schema_summaries,
                        )
                    )
                    continue
                except Exception as e:
                    # Fallback in case of connection issues
                    print(f"Error browsing dynamic schemas: {e}")

            schemas = sorted(catalog.schemas, key=lambda item: item.name.lower())
            result.append(
                CatalogSummary(
                    id=catalog.id,
                    name=catalog.name,
                    description=catalog.description,
                    catalog_type=catalog.catalog_type,
                    connection_id=catalog.connection_id,
                    database_name=catalog.database_name,
                    schema_count=len(schemas),
                    table_count=sum(len(schema.tables) for schema in schemas),
                    schemas=[
                        CatalogSchemaSummary(
                            id=schema.id,
                            name=schema.name,
                            description=schema.description,
                            table_count=len(schema.tables),
                        )
                        for schema in schemas
                    ],
                )
            )
        return result

def list_catalogs(db: Session, workspace_id: str | None=None) -> list[CatalogSummary]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = ListCatalogs(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, workspace_id)
