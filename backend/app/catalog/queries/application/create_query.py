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

class CreateQuery:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, body: QueryCreate, user: dict) -> UnifiedCatalogQuery:
        from app.catalog.runtime import _current_actor
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name
        ).first()
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        # Check for duplicate name in this catalog & schema
        existing = db.query(UnifiedCatalogQuery).filter(
            UnifiedCatalogQuery.catalog_name == catalog_name,
            UnifiedCatalogQuery.schema_name == schema_name,
            UnifiedCatalogQuery.name == body.name
        ).first()
        if existing:
            raise ValueError(f"Query '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")

        actor = _current_actor(user)

        catalog_query = UnifiedCatalogQuery(
            schema_id=schema.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            name=body.name,
            sql_text=body.sql_text,
            owner=actor,
            description=body.description,
            current_version=1,
            created_by=actor,
            updated_by=actor,
        )
        db.add(catalog_query)
        db.flush()

        # Automatically create version 1
        v1 = UnifiedCatalogQueryVersion(
            query_id=catalog_query.id,
            version=1,
            sql_text=body.sql_text,
            description=body.description,
            change_summary="Initial version",
            created_by=actor,
        )
        db.add(v1)
        db.commit()
        db.refresh(catalog_query)

        # Enqueue embedding for semantic search
        q_name = catalog_query.name
        try:
            self.search_index.enqueue(
                db,
                object_type="query",
                source_object_id=catalog_query.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=catalog_query.name,
                description=catalog_query.description or catalog_query.sql_text,
            )
            db.commit()
        except Exception as _idx_err:
            db.rollback()
            import logging as _log
            self.log.warning("Failed to enqueue embedding for query %s: %s", q_name, _idx_err)

        return catalog_query

async def create_query(db: Session, catalog_name: str, schema_name: str, body: QueryCreate, user: dict) -> UnifiedCatalogQuery:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateQuery(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, body, user)
