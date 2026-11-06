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

class MoveDashboard:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, dashboard_name: str, body: DashboardMove, user: dict) -> UnifiedCatalogDashboard:
        from app.catalog.runtime import get_dashboard, _current_actor
        catalog_dashboard = get_dashboard(db, catalog_name, schema_name, dashboard_name)

        target_catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == body.target_catalog).first()
        if not target_catalog:
            raise ValueError(f"Target catalog '{body.target_catalog}' not found.")

        target_schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == target_catalog.id,
            UnifiedCatalogSchema.name == body.target_schema
        ).first()
        if not target_schema:
            raise ValueError(f"Target schema '{body.target_schema}' not found in catalog '{body.target_catalog}'.")

        dest_name = body.new_name if body.new_name else catalog_dashboard.name

        # Check for name uniqueness in target schema
        existing = db.query(UnifiedCatalogDashboard).filter(
            UnifiedCatalogDashboard.catalog_name == body.target_catalog,
            UnifiedCatalogDashboard.schema_name == body.target_schema,
            UnifiedCatalogDashboard.name == dest_name
        ).first()
        if existing:
            raise ValueError(f"Dashboard '{dest_name}' already exists in target schema '{body.target_catalog}.{body.target_schema}'.")

        actor = _current_actor(user)
        catalog_dashboard.catalog_name = body.target_catalog
        catalog_dashboard.schema_name = body.target_schema
        catalog_dashboard.schema_id = target_schema.id
        catalog_dashboard.name = dest_name
        catalog_dashboard.updated_by = actor

        # Also rename the system dashboard if name changed
        if body.new_name and catalog_dashboard.dashboard_id:
            from app.dashboards.models.dashboard import Dashboard
            system_dash = db.query(Dashboard).filter(Dashboard.id == catalog_dashboard.dashboard_id).first()
            if system_dash:
                system_dash.name = dest_name

        db.commit()
        db.refresh(catalog_dashboard)
        return catalog_dashboard

async def move_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str, body: DashboardMove, user: dict) -> UnifiedCatalogDashboard:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = MoveDashboard(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, dashboard_name, body, user)
