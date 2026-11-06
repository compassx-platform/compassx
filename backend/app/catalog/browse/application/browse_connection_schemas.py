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

class BrowseConnectionSchemas:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, connection_id: int | str, database: str) -> list[RemoteSchemaRead]:
        from app.catalog.runtime import _get_connection, _connect_record
        record = _get_connection(db, connection_id)
        conn = _connect_record(record, database)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT schema_name AS name,
                       schema_owner AS owner
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                  AND schema_name NOT LIKE 'pg_temp_%'
                  AND schema_name NOT LIKE 'pg_toast_temp_%'
                ORDER BY schema_name
                """
            )
            return [RemoteSchemaRead(**dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()

def browse_connection_schemas(db: Session, connection_id: int | str, database: str) -> list[RemoteSchemaRead]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = BrowseConnectionSchemas(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, connection_id, database)
