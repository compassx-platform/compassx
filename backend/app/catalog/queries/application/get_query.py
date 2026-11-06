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

class GetQuery:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str) -> UnifiedCatalogQuery:
        query_obj = db.query(UnifiedCatalogQuery).options(
            joinedload(UnifiedCatalogQuery.versions)
        ).filter(
            UnifiedCatalogQuery.catalog_name == catalog_name,
            UnifiedCatalogQuery.schema_name == schema_name,
            UnifiedCatalogQuery.name == query_name
        ).first()
        if not query_obj:
            raise ValueError(f"Query '{query_name}' not found in schema '{catalog_name}.{schema_name}'.")
        return query_obj

def get_query(db: Session, catalog_name: str, schema_name: str, query_name: str) -> UnifiedCatalogQuery:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = GetQuery(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, query_name)
