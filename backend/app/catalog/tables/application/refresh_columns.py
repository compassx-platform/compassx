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

class RefreshColumns:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, fqn: str) -> CatalogTableRead:
        from app.catalog.runtime import _parse_fqn, introspect_columns, _replace_columns, get_table
        catalog_name, schema_name, table_name = _parse_fqn(fqn)
        table = (
            db.query(UnifiedCatalogTable)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
            .filter(
                UnifiedCatalog.name == catalog_name,
                UnifiedCatalogSchema.name == schema_name,
                UnifiedCatalogTable.name == table_name,
            )
            .first()
        )
        if not table:
            raise ValueError(f"Table '{fqn}' not found")
        columns = introspect_columns(db, table)
        _replace_columns(db, table, columns)
        return get_table(db, fqn)

def refresh_columns(db: Session, fqn: str) -> CatalogTableRead:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = RefreshColumns(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, fqn)
