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

class CreateIcebergSchema:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, storage_backend_name: str, user: dict, description: str | None=None) -> dict:
        from app.catalog.runtime import _current_actor
        """
        Create an Iceberg schema:
        1. Resolves the storage backend and computes a base_path.
        2. Upserts the schema row in Postgres with storage_backend_id + base_path.
        3. Writes a .schema marker file to blob storage.
        """
        from app.storage.db_models import StorageBackend
        from app.storage.service import storage_service
        from app.catalog.iceberg_manager import IcebergManager
        from app.catalog.storage_context import _get_backend_base

        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found")

        backend_row = db.query(StorageBackend).filter(StorageBackend.name == storage_backend_name).first()
        if not backend_row:
            raise ValueError(f"Storage backend '{storage_backend_name}' not found")

        backend_base = _get_backend_base(backend_row)

        # base_path stored in DB = absolute from container root (used by DuckDB)
        base_path = f"{backend_base}{catalog_name}/{schema_name}/"
        # relative path passed to IcebergManager (it will prepend backend.base_path internally)
        iceberg_relative = f"{catalog_name}/{schema_name}"

        actor = _current_actor(user)
        existing = (
            db.query(UnifiedCatalogSchema)
            .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
            .first()
        )
        if existing:
            existing.storage_backend_id = backend_row.id
            existing.base_path = base_path
            if description:
                existing.description = description
            schema = existing
        else:
            schema = UnifiedCatalogSchema(
                catalog_id=catalog.id,
                name=schema_name,
                description=description,
                storage_backend_id=backend_row.id,
                base_path=base_path,
                created_by=actor,
            )
            db.add(schema)

        db.commit()

        backend = storage_service.get_backend(db, storage_backend_name)
        # Pass relative path — backend prepends its own base_path internally
        try:
            await IcebergManager(backend).create_schema(iceberg_relative)
        except Exception as e:
            import logging
            self.log.warning("Failed to write Iceberg schema marker to blob storage: %s", e)

        return {
            "catalog": catalog_name,
            "schema": schema_name,
            "base_path": base_path,
            "storage_backend": storage_backend_name,
        }

async def create_iceberg_schema(db: Session, catalog_name: str, schema_name: str, storage_backend_name: str, user: dict, description: str | None=None) -> dict:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateIcebergSchema(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, storage_backend_name, user, description)
