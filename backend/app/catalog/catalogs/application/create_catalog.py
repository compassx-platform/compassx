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

class CreateCatalog:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, body: CatalogCreate, user: dict) -> UnifiedCatalog:
        existing = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.name).first()
        if existing:
            raise ValueError(f"Catalog with name '{body.name}' already exists.")
        actor = user.get("email", "system")
        catalog = UnifiedCatalog(
            name=body.name,
            description=body.description,
            catalog_type=body.catalog_type,
            connection_id=body.connection_id,
            database_name=body.database_name,
            storage_backend_id=body.storage_backend_id,
            base_path=body.base_path,
            created_by=actor,
        )
        db.add(catalog)
        db.commit()
        db.refresh(catalog)
        return catalog

def create_catalog(db: Session, body: CatalogCreate, user: dict) -> UnifiedCatalog:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateCatalog(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, body, user)
