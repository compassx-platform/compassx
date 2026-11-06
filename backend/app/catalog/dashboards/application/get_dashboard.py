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

class GetDashboard:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, dashboard_name: str) -> UnifiedCatalogDashboard:
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name
        ).first()
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        dashboard = db.query(UnifiedCatalogDashboard).filter(
            UnifiedCatalogDashboard.schema_id == schema.id,
            UnifiedCatalogDashboard.name == dashboard_name
        ).first()
        if not dashboard:
            raise ValueError(f"Dashboard '{dashboard_name}' not found in schema '{catalog_name}.{schema_name}'.")
        return dashboard

def get_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str) -> UnifiedCatalogDashboard:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = GetDashboard(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, dashboard_name)
