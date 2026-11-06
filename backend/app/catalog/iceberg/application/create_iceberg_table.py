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

class CreateIcebergTable:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, table_name: str, columns: list[dict], user: dict, description: str | None=None, properties: dict | None=None) -> UnifiedCatalogTable:
        from app.catalog.runtime import _current_actor
        """
        Create an Iceberg table:
        1. Resolves the schema's storage backend.
        2. Writes Iceberg v2 metadata JSON to blob storage.
        3. Creates the table row in Postgres with metadata_location set.
        """
        from app.catalog.iceberg_manager import IcebergManager

        if properties is None:
            properties = {}

        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found")

        schema = (
            db.query(UnifiedCatalogSchema)
            .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
            .first()
        )
        if not schema:
            raise ValueError(f"Schema '{catalog_name}.{schema_name}' not found")

        ctx = resolve_catalog_storage(db, catalog_name, schema_name)
        if not ctx:
            raise ValueError(
                f"No storage backend configured for schema '{schema_name}' or its parent catalog '{catalog_name}'. "
                "Use POST /iceberg/schemas to configure storage first."
            )

        table_path_abs = ctx.abs_path(f"tables/{table_name}")
        table_path_rel = ctx.rel_path(f"tables/{table_name}")

        mgr = IcebergManager(ctx.backend)

        if await mgr.table_exists(table_path_rel):
            raise ValueError(
                f"Iceberg metadata already exists at {table_path_abs}. "
                "The table name is already in use on blob storage."
            )

        metadata_location_rel = await mgr.create_table(
            table_path=table_path_rel,
            table_name=table_name,
            columns=columns,
            properties=properties,
        )
        # Convert relative metadata location back to absolute for DB storage
        metadata_location_abs = f"{ctx.backend_base}{metadata_location_rel}"

        actor = _current_actor(user)
        existing = (
            db.query(UnifiedCatalogTable)
            .filter(UnifiedCatalogTable.schema_id == schema.id, UnifiedCatalogTable.name == table_name)
            .first()
        )
        if existing:
            raise ValueError(f"Table '{table_name}' already exists in schema '{schema_name}'")

        table = UnifiedCatalogTable(
            schema_id=schema.id,
            name=table_name,
            table_type=CatalogTableType.ICEBERG,
            metadata_location=metadata_location_abs,
            storage_location=table_path_abs,
            description=description,
            owner=actor,
            created_by=actor,
            properties=properties,
        )
        db.add(table)
        db.commit()
        db.refresh(table)

        # Enqueue embedding for semantic search (column summary built from columns list)
        try:
            col_summary = ", ".join(
                f"{c['name']} ({c.get('type', '')})".strip() for c in columns
            ) if columns else None
            self.search_index.enqueue(
                db,
                object_type="table",
                source_object_id=table.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=table_name,
                description=description,
                content_summary=col_summary,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            self.log.warning("Failed to enqueue embedding for iceberg table %s: %s", table_name, _idx_err)

        return table

async def create_iceberg_table(db: Session, catalog_name: str, schema_name: str, table_name: str, columns: list[dict], user: dict, description: str | None=None, properties: dict | None=None) -> UnifiedCatalogTable:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateIcebergTable(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, table_name, columns, user, description, properties)
