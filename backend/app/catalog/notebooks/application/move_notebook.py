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

class MoveNotebook:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, notebook_name: str, body: NotebookMove, user: dict) -> UnifiedCatalogNotebook:
        from app.catalog.runtime import get_notebook, _current_actor, _read_notebook_content, _write_notebook_content, _delete_notebook_file
        notebook = get_notebook(db, catalog_name, schema_name, notebook_name)

        target_catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.target_catalog).first()
        if not target_catalog:
            raise ValueError(f"Target catalog '{body.target_catalog}' not found.")

        target_schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == target_catalog.id,
            UnifiedCatalogSchema.name == body.target_schema
        ).first()
        if not target_schema:
            raise ValueError(f"Target schema '{body.target_schema}' not found in catalog '{body.target_catalog}'.")

        dest_name = body.new_name if body.new_name else notebook.name

        # Check for name uniqueness in target schema
        existing = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.catalog_name == body.target_catalog,
            UnifiedCatalogNotebook.schema_name == body.target_schema,
            UnifiedCatalogNotebook.name == dest_name
        ).first()
        if existing:
            raise ValueError(f"Notebook '{dest_name}' already exists in target schema '{body.target_catalog}.{body.target_schema}'.")

        old_schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == notebook.schema_id).first()
        if old_schema and old_schema.id != target_schema.id:
            try:
                content = await _read_notebook_content(db, old_schema, notebook.blob_path)
                await _write_notebook_content(db, target_schema, notebook.blob_path, content)
                await _delete_notebook_file(db, old_schema, notebook.blob_path)
            except Exception as exc:
                import logging
                self.log.warning(f"Failed to physically move notebook file {notebook.blob_path}: {exc}")

        actor = _current_actor(user)
        notebook.catalog_name = body.target_catalog
        notebook.schema_name = body.target_schema
        notebook.schema_id = target_schema.id
        notebook.name = dest_name
        notebook.updated_by = actor

        db.commit()
        db.refresh(notebook)
        return notebook

async def move_notebook(db: Session, catalog_name: str, schema_name: str, notebook_name: str, body: NotebookMove, user: dict) -> UnifiedCatalogNotebook:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = MoveNotebook(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, notebook_name, body, user)
