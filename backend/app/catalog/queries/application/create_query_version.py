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

class CreateQueryVersion:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryCreateVersion, user: dict) -> UnifiedCatalogQueryVersion:
        from app.catalog.runtime import get_query, _current_actor
        catalog_query = get_query(db, catalog_name, schema_name, query_name)
        actor = _current_actor(user)

        highest_v = db.query(func.max(UnifiedCatalogQueryVersion.version)).filter(
            UnifiedCatalogQueryVersion.query_id == catalog_query.id
        ).scalar() or catalog_query.current_version
        next_v = highest_v + 1

        new_v = UnifiedCatalogQueryVersion(
            query_id=catalog_query.id,
            version=next_v,
            sql_text=body.sql_text,
            description=body.description or catalog_query.description,
            change_summary=body.change_summary or f"Version {next_v}",
            created_by=actor,
        )
        db.add(new_v)
        catalog_query.sql_text = body.sql_text
        if body.description is not None:
            catalog_query.description = body.description
        catalog_query.current_version = next_v
        catalog_query.updated_by = actor

        db.commit()
        db.refresh(new_v)
        db.refresh(catalog_query)

        # Re-enqueue embedding
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
            self.log.warning("Failed to re-enqueue embedding for query %s: %s", catalog_query.name, _idx_err)

        return new_v

def create_query_version(db: Session, catalog_name: str, schema_name: str, query_name: str, body: QueryCreateVersion, user: dict) -> UnifiedCatalogQueryVersion:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateQueryVersion(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, query_name, body, user)
