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

class CreateVolume:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, body: VolumeCreate, user: dict):
        from app.catalog.runtime import _current_actor
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")

        schema = (
            db.query(UnifiedCatalogSchema)
            .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
            .first()
        )
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        ctx = resolve_catalog_storage(db, catalog_name, schema_name)
        if not ctx:
            raise ValueError(
                f"No storage backend configured for schema '{schema_name}' or its parent catalog '{catalog_name}'. "
                "Bind a blob storage backend to the catalog or schema first."
            )

        from app.catalog.models import UnifiedCatalogVolume
        existing = (
            db.query(UnifiedCatalogVolume)
            .filter(UnifiedCatalogVolume.schema_id == schema.id, UnifiedCatalogVolume.name == body.name)
            .first()
        )
        if existing:
            raise ValueError(f"Volume '{body.name}' already exists in schema '{schema_name}'.")

        actor = _current_actor(user)
        storage_loc = ctx.abs_path(f"volumes/{body.name}/")
        rel_path = ctx.rel_path(f"volumes/{body.name}/.keep")
        await ctx.backend.write_bytes(rel_path, b"", "application/octet-stream")

        volume = UnifiedCatalogVolume(
            schema_id=schema.id,
            name=body.name,
            description=body.description,
            storage_location=storage_loc,
            owner=actor,
            created_by=actor
        )
        db.add(volume)
        db.commit()
        db.refresh(volume)

        # Enqueue embedding for semantic search
        try:
            self.search_index.enqueue(
                db,
                object_type="volume",
                source_object_id=volume.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=volume.name,
                description=volume.description,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            self.log.warning("Failed to enqueue embedding for volume %s: %s", volume.name, _idx_err)

        return volume

async def create_volume(db: Session, catalog_name: str, schema_name: str, body: VolumeCreate, user: dict):
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateVolume(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, body, user)
