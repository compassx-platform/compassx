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

class UpdateNotebook:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, notebook_name: str, body: NotebookUpdate, user: dict) -> UnifiedCatalogNotebook:
        from app.catalog.runtime import get_notebook, _current_actor
        notebook = get_notebook(db, catalog_name, schema_name, notebook_name)

        actor = _current_actor(user)
        if body.comment is not None:
            notebook.comment = body.comment
        if body.owner is not None:
            notebook.owner = body.owner
        if body.name is not None and body.name != notebook.name:
            # Check name uniqueness in target schema
            existing = db.query(UnifiedCatalogNotebook).filter(
                UnifiedCatalogNotebook.catalog_name == catalog_name,
                UnifiedCatalogNotebook.schema_name == schema_name,
                UnifiedCatalogNotebook.name == body.name
            ).first()
            if existing:
                raise ValueError(f"Notebook '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")
            notebook.name = body.name

        notebook.updated_by = actor
        db.commit()
        db.refresh(notebook)

        # Re-enqueue embedding whenever name or comment changes (metadata fields per spec §4)
        if body.name is not None or body.comment is not None:
            try:
                self.search_index.enqueue(
                    db,
                    object_type="notebook",
                    source_object_id=notebook.id,
                    catalog_name=notebook.catalog_name,
                    schema_name=notebook.schema_name,
                    object_name=notebook.name,
                    description=notebook.comment,
                )
                db.commit()
            except Exception as _idx_err:
                import logging as _log
                self.log.warning("Failed to re-enqueue embedding for notebook %s: %s", notebook.name, _idx_err)

        return notebook

def update_notebook(db: Session, catalog_name: str, schema_name: str, notebook_name: str, body: NotebookUpdate, user: dict) -> UnifiedCatalogNotebook:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = UpdateNotebook(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, notebook_name, body, user)
