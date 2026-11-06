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

class UpdateQuery:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryUpdate, user: dict) -> UnifiedCatalogQuery:
        from app.catalog.runtime import get_query, _current_actor
        catalog_query = get_query(db, catalog_name, schema_name, query_name)
        actor = _current_actor(user)

        if body.owner is not None:
            catalog_query.owner = body.owner
        if body.description is not None:
            catalog_query.description = body.description

        # If SQL text changed, create a new version automatically
        if body.sql_text is not None and body.sql_text != catalog_query.sql_text:
            highest_v = db.query(func.max(UnifiedCatalogQueryVersion.version)).filter(
                UnifiedCatalogQueryVersion.query_id == catalog_query.id
            ).scalar() or catalog_query.current_version
            next_v = highest_v + 1
            new_v = UnifiedCatalogQueryVersion(
                query_id=catalog_query.id,
                version=next_v,
                sql_text=body.sql_text,
                description=body.description or catalog_query.description,
                change_summary=body.change_summary or f"Updated query to version {next_v}",
                created_by=actor,
            )
            db.add(new_v)
            catalog_query.sql_text = body.sql_text
            catalog_query.current_version = next_v

        if body.name is not None and body.name != catalog_query.name:
            existing = db.query(UnifiedCatalogQuery).filter(
                UnifiedCatalogQuery.catalog_name == catalog_name,
                UnifiedCatalogQuery.schema_name == schema_name,
                UnifiedCatalogQuery.name == body.name
            ).first()
            if existing:
                raise ValueError(f"Query '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")
            catalog_query.name = body.name

        catalog_query.updated_by = actor
        db.commit()
        db.refresh(catalog_query)

        # Re-enqueue embedding whenever name, description, or SQL changes
        q_name = catalog_query.name
        try:
            self.search_index.enqueue(
                db,
                object_type="query",
                source_object_id=catalog_query.id,
                catalog_name=catalog_query.catalog_name,
                schema_name=catalog_query.schema_name,
                object_name=catalog_query.name,
                description=catalog_query.description or catalog_query.sql_text,
            )
            db.commit()
        except Exception as _idx_err:
            db.rollback()
            import logging as _log
            self.log.warning("Failed to re-enqueue embedding for query %s: %s", q_name, _idx_err)

        return catalog_query

def update_query(db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryUpdate, user: dict) -> UnifiedCatalogQuery:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = UpdateQuery(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, query_name, body, user)
