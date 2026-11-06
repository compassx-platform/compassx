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

class GetQueryVersion:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str, version_num: int) -> UnifiedCatalogQueryVersion:
        from app.catalog.runtime import get_query
        catalog_query = get_query(db, catalog_name, schema_name, query_name)
        v = db.query(UnifiedCatalogQueryVersion).filter(
            UnifiedCatalogQueryVersion.query_id == catalog_query.id,
            UnifiedCatalogQueryVersion.version == version_num
        ).first()
        if not v:
            raise ValueError(f"Version {version_num} not found for query '{query_name}'.")
        return v

def get_query_version(db: Session, catalog_name: str, schema_name: str, query_name: str, version_num: int) -> UnifiedCatalogQueryVersion:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = GetQueryVersion(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, query_name, version_num)
