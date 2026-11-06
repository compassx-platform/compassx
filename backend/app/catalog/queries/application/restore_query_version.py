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

class RestoreQueryVersion:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, query_name: str, version_num: int, user: dict) -> UnifiedCatalogQuery:
        from app.catalog.runtime import get_query_version, get_query, _current_actor
        target_v = get_query_version(db, catalog_name, schema_name, query_name, version_num)
        catalog_query = get_query(db, catalog_name, schema_name, query_name)
        actor = _current_actor(user)

        highest_v = db.query(func.max(UnifiedCatalogQueryVersion.version)).filter(
            UnifiedCatalogQueryVersion.query_id == catalog_query.id
        ).scalar() or catalog_query.current_version
        next_v = highest_v + 1

        new_v = UnifiedCatalogQueryVersion(
            query_id=catalog_query.id,
            version=next_v,
            sql_text=target_v.sql_text,
            description=target_v.description,
            change_summary=f"Restored from version {version_num}",
            created_by=actor,
        )
        db.add(new_v)
        catalog_query.sql_text = target_v.sql_text
        catalog_query.description = target_v.description
        catalog_query.current_version = next_v
        catalog_query.updated_by = actor

        db.commit()
        db.refresh(catalog_query)
        return catalog_query

def restore_query_version(db: Session, catalog_name: str, schema_name: str, query_name: str, version_num: int, user: dict) -> UnifiedCatalogQuery:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = RestoreQueryVersion(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, query_name, version_num, user)
