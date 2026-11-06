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

class MoveQuery:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryMove, user: dict) -> UnifiedCatalogQuery:
        from app.catalog.runtime import get_query, _current_actor
        catalog_query = get_query(db, catalog_name, schema_name, query_name)

        target_catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.target_catalog).first()
        if not target_catalog:
            raise ValueError(f"Target catalog '{body.target_catalog}' not found.")

        target_schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == target_catalog.id,
            UnifiedCatalogSchema.name == body.target_schema
        ).first()
        if not target_schema:
            raise ValueError(f"Target schema '{body.target_schema}' not found in catalog '{body.target_catalog}'.")

        dest_name = body.new_name if body.new_name else catalog_query.name

        existing = db.query(UnifiedCatalogQuery).filter(
            UnifiedCatalogQuery.catalog_name == body.target_catalog,
            UnifiedCatalogQuery.schema_name == body.target_schema,
            UnifiedCatalogQuery.name == dest_name
        ).first()
        if existing:
            raise ValueError(f"Query '{dest_name}' already exists in target schema '{body.target_catalog}.{body.target_schema}'.")

        actor = _current_actor(user)
        catalog_query.catalog_name = body.target_catalog
        catalog_query.schema_name = body.target_schema
        catalog_query.schema_id = target_schema.id
        catalog_query.name = dest_name
        catalog_query.updated_by = actor

        db.commit()
        db.refresh(catalog_query)
        return catalog_query

async def move_query(db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryMove, user: dict) -> UnifiedCatalogQuery:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = MoveQuery(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, query_name, body, user)
