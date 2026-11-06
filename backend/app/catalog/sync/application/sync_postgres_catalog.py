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

class SyncPostgresCatalog:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, triggered_by: str) -> dict:
        from app.catalog.runtime import _get_connection, _connect_record
        """Walk a postgres catalog via information_schema and persist schemas,
        tables, and columns into the catalog tables, then enqueue embeddings.

        Returns a summary dict: {schemas_synced, tables_synced, columns_synced}.
        """
        import logging as _log
        logger = self.log

        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found")
        if catalog.catalog_type != "postgres":
            raise ValueError(f"Catalog '{catalog_name}' is not a postgres catalog")
        if not catalog.connection_id or not catalog.database_name:
            raise ValueError(f"Catalog '{catalog_name}' has no connection_id or database_name configured")

        record = _get_connection(db, catalog.connection_id)
        pg_conn = _connect_record(record, catalog.database_name)

        try:
            cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Fetch all user schemas
            cur.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema',
                                           'pg_toast', 'catalog_search')
                  AND schema_name NOT LIKE 'pg_temp_%'
                  AND schema_name NOT LIKE 'pg_toast_temp_%'
                ORDER BY schema_name
                """
            )
            remote_schemas = [r["schema_name"] for r in cur.fetchall()]

            # Fetch all tables in one query
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema',
                                           'pg_toast', 'catalog_search')
                  AND table_schema NOT LIKE 'pg_temp_%'
                ORDER BY table_schema, table_name
                """
            )
            remote_tables = cur.fetchall()

            # Fetch all columns in one query
            cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type, is_nullable, ordinal_position
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema',
                                           'pg_toast', 'catalog_search')
                  AND table_schema NOT LIKE 'pg_temp_%'
                ORDER BY table_schema, table_name, ordinal_position
                """
            )
            remote_columns = cur.fetchall()
        finally:
            pg_conn.close()

        # Build column map: (schema, table) -> [col_dicts]
        col_map: dict[tuple[str, str], list[dict]] = {}
        for col in remote_columns:
            key = (col["table_schema"], col["table_name"])
            col_map.setdefault(key, []).append(dict(col))


        schemas_synced = 0
        tables_synced = 0
        columns_synced = 0

        # Group tables by schema
        tables_by_schema: dict[str, list] = {}
        for tbl in remote_tables:
            tables_by_schema.setdefault(tbl["table_schema"], []).append(tbl["table_name"])

        for schema_name in remote_schemas:
            # Upsert schema row
            schema_row = (
                db.query(UnifiedCatalogSchema)
                .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
                .first()
            )
            if not schema_row:
                schema_row = UnifiedCatalogSchema(
                    catalog_id=catalog.id,
                    name=schema_name,
                    created_by=triggered_by,
                )
                db.add(schema_row)
                db.flush()
            schemas_synced += 1

            for table_name in tables_by_schema.get(schema_name, []):
                # Upsert table row
                table_row = (
                    db.query(UnifiedCatalogTable)
                    .filter(UnifiedCatalogTable.schema_id == schema_row.id, UnifiedCatalogTable.name == table_name)
                    .first()
                )
                if not table_row:
                    table_row = UnifiedCatalogTable(
                        schema_id=schema_row.id,
                        name=table_name,
                        table_type=CatalogTableType.POSTGRES_NATIVE,
                        connection_id=catalog.connection_id,
                        source_database=catalog.database_name,
                        pg_schema=schema_name,
                        pg_table=table_name,
                        owner=triggered_by,
                        created_by=triggered_by,
                    )
                    db.add(table_row)
                    db.flush()
                else:
                    # Update connection info in case it changed
                    table_row.connection_id = catalog.connection_id
                    table_row.source_database = catalog.database_name
                    table_row.pg_schema = schema_name
                    table_row.pg_table = table_name
                    db.flush()
                tables_synced += 1

                # Replace columns (delete + insert)
                db.query(UnifiedCatalogColumn).filter(UnifiedCatalogColumn.table_id == table_row.id).delete()
                cols = col_map.get((schema_name, table_name), [])
                for col in cols:
                    db.add(UnifiedCatalogColumn(
                        table_id=table_row.id,
                        name=col["column_name"],
                        data_type=col["data_type"],
                        nullable=(col["is_nullable"] == "YES"),
                        ordinal=col["ordinal_position"],
                    ))
                columns_synced += len(cols)

                # Enqueue embedding
                col_summary = ", ".join(
                    f"{c['column_name']} ({c['data_type']})" for c in cols
                ) if cols else None
                try:
                    self.search_index.enqueue(
                        db,
                        object_type="table",
                        source_object_id=table_row.id,
                        catalog_name=catalog_name,
                        schema_name=schema_name,
                        object_name=table_name,
                        content_summary=col_summary,
                    )
                except Exception as emb_err:
                    logger.warning("Failed to enqueue embedding for %s.%s.%s: %s", catalog_name, schema_name, table_name, emb_err)

        db.commit()
        logger.info("Postgres catalog sync done: catalog=%s schemas=%d tables=%d columns=%d", catalog_name, schemas_synced, tables_synced, columns_synced)
        return {"schemas_synced": schemas_synced, "tables_synced": tables_synced, "columns_synced": columns_synced}

def sync_postgres_catalog(db: Session, catalog_name: str, triggered_by: str) -> dict:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = SyncPostgresCatalog(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, triggered_by)
