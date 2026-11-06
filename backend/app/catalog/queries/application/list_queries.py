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

class ListQueries:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str) -> list[UnifiedCatalogQuery]:
        schema = db.query(UnifiedCatalogSchema).join(
            UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id
        ).filter(
            UnifiedCatalog.name == catalog_name,
            UnifiedCatalogSchema.name == schema_name
        ).first()
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        return db.query(UnifiedCatalogQuery).options(
            joinedload(UnifiedCatalogQuery.versions)
        ).filter(
            UnifiedCatalogQuery.schema_id == schema.id
        ).order_by(UnifiedCatalogQuery.created_at.desc()).all()

def list_queries(db: Session, catalog_name: str, schema_name: str) -> list[UnifiedCatalogQuery]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = ListQueries(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name)
