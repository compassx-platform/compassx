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

class BrowseConnectionTables:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, connection_id: int | str, database: str, schema_name: str) -> list[RemoteTableRead]:
        from app.catalog.runtime import _get_connection, _connect_record
        record = _get_connection(db, connection_id)
        conn = _connect_record(record, database)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT t.table_name AS name,
                       t.table_schema AS schema_name,
                       t.table_type,
                       s.n_live_tup::bigint AS row_estimate
                FROM information_schema.tables t
                LEFT JOIN pg_stat_user_tables s
                       ON s.schemaname = t.table_schema
                      AND s.relname = t.table_name
                WHERE t.table_schema = %s
                ORDER BY t.table_type, t.table_name
                """,
                (schema_name,),
            )
            return [RemoteTableRead(**dict(row)) for row in cur.fetchall()]
        finally:
            conn.close()

def browse_connection_tables(db: Session, connection_id: int | str, database: str, schema_name: str) -> list[RemoteTableRead]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = BrowseConnectionTables(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, connection_id, database, schema_name)
