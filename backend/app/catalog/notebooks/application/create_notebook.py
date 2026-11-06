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

class CreateNotebook:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, body: NotebookCreate, user: dict) -> UnifiedCatalogNotebook:
        from app.catalog.runtime import _current_actor, _write_notebook_content
        from uuid import uuid4

        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name
        ).first()
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        # Check for name namespace conflict
        existing = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.catalog_name == catalog_name,
            UnifiedCatalogNotebook.schema_name == schema_name,
            UnifiedCatalogNotebook.name == body.name
        ).first()
        if existing:
            raise ValueError(f"Notebook '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")

        # Write empty skeleton to storage
        nb_id = str(uuid4())
        rel_path = f"{nb_id}.ipynb"

        empty_nb = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [],
        }
        content = body.initial_content if body.initial_content else empty_nb

        await _write_notebook_content(db, schema, rel_path, content)

        actor = _current_actor(user)
        notebook = UnifiedCatalogNotebook(
            schema_id=schema.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            name=body.name,
            blob_path=rel_path,
            owner=actor,
            comment=body.comment,
            created_by=actor,
            updated_by=actor,
        )
        db.add(notebook)
        db.commit()
        db.refresh(notebook)

        # Enqueue embedding for semantic search
        try:
            self.search_index.enqueue(
                db,
                object_type="notebook",
                source_object_id=notebook.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=notebook.name,
                description=notebook.comment,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            self.log.warning("Failed to enqueue embedding for notebook %s: %s", notebook.name, _idx_err)

        return notebook

async def create_notebook(db: Session, catalog_name: str, schema_name: str, body: NotebookCreate, user: dict) -> UnifiedCatalogNotebook:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateNotebook(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, body, user)
