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

class CreateSchema:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, body: SchemaCreate, user: dict) -> UnifiedCatalogSchema:
        from app.catalog.runtime import _current_actor
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")

        existing = (
            db.query(UnifiedCatalogSchema)
            .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == body.name)
            .first()
        )
        if existing:
            raise ValueError(f"Schema with name '{body.name}' already exists in catalog '{catalog_name}'.")

        actor = _current_actor(user)
        schema = UnifiedCatalogSchema(
            catalog_id=catalog.id,
            name=body.name,
            description=body.description,
            created_by=actor
        )
        db.add(schema)
        db.commit()
        db.refresh(schema)
        return schema

def create_schema(db: Session, catalog_name: str, body: SchemaCreate, user: dict) -> UnifiedCatalogSchema:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateSchema(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, body, user)
