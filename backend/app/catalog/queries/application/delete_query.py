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

class DeleteQuery:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str) -> None:
        from app.catalog.runtime import get_query
        catalog_query = get_query(db, catalog_name, schema_name, query_name)

        # Delete search indexing entry
        try:
            self.search_index.delete(db, "query", catalog_query.id)
        except Exception as _idx_err:
            db.rollback()
            import logging as _log
            self.log.warning("Failed to delete embedding for query %s: %s", catalog_query.name, _idx_err)

        db.delete(catalog_query)
        db.commit()

async def delete_query(db: Session, catalog_name: str, schema_name: str, query_name: str) -> None:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = DeleteQuery(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, query_name)
