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

class DeleteSchema:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str) -> None:
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name
        ).first()
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        # Check if there are any notebooks blocking deletion
        blocking_notebooks = db.query(UnifiedCatalogNotebook).filter(
            UnifiedCatalogNotebook.schema_id == schema.id
        ).all()
        if blocking_notebooks:
            names = ", ".join([nb.name for nb in blocking_notebooks])
            raise ValueError(f"Cannot delete schema '{schema_name}' because it contains registered notebooks: {names}.")

        # Check if there are any dashboards blocking deletion
        blocking_dashboards = db.query(UnifiedCatalogDashboard).filter(
            UnifiedCatalogDashboard.schema_id == schema.id
        ).all()
        if blocking_dashboards:
            names = ", ".join([db_item.name for db_item in blocking_dashboards])
            raise ValueError(f"Cannot delete schema '{schema_name}' because it contains registered dashboards: {names}.")

        db.delete(schema)
        db.commit()

def delete_schema(db: Session, catalog_name: str, schema_name: str) -> None:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = DeleteSchema(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name)
