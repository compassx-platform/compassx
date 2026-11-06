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

class CreateTable:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, body: TableCreate, user: dict) -> UnifiedCatalogTable:
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

        existing = (
            db.query(UnifiedCatalogTable)
            .filter(UnifiedCatalogTable.schema_id == schema.id, UnifiedCatalogTable.name == body.name)
            .first()
        )
        if existing:
            raise ValueError(f"Table '{body.name}' already exists in schema '{schema_name}'.")

        actor = _current_actor(user)
        table = UnifiedCatalogTable(
            schema_id=schema.id,
            name=body.name,
            description=body.description,
            table_type=body.table_type,
            owner=actor,
            created_by=actor
        )
        db.add(table)
        db.commit()
        db.refresh(table)

        # Enqueue embedding for semantic search
        try:
            col_summary = None
            self.search_index.enqueue(
                db,
                object_type="table",
                source_object_id=table.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=table.name,
                description=table.description,
                content_summary=col_summary,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            self.log.warning("Failed to enqueue embedding for table %s: %s", table.name, _idx_err)

        return table

def create_table(db: Session, catalog_name: str, schema_name: str, body: TableCreate, user: dict) -> UnifiedCatalogTable:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateTable(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, body, user)
