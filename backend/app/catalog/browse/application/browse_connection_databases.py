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

class BrowseConnectionDatabases:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, connection_id: int | str) -> list[RemoteDatabaseRead]:
        from app.catalog.runtime import _get_connection, _connect_record
        record = _get_connection(db, connection_id)
        conn = _connect_record(record)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT datname AS name,
                       pg_catalog.pg_get_userbyid(datdba) AS owner
                FROM pg_catalog.pg_database
                WHERE datistemplate = false
                ORDER BY datname
                """
            )
            return [RemoteDatabaseRead(**dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()

def browse_connection_databases(db: Session, connection_id: int | str) -> list[RemoteDatabaseRead]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = BrowseConnectionDatabases(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, connection_id)
