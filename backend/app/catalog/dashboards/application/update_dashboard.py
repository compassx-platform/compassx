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

class UpdateDashboard:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, dashboard_name: str, body: DashboardUpdate, user: dict) -> UnifiedCatalogDashboard:
        from app.catalog.runtime import get_dashboard, _current_actor
        from app.dashboards.models.dashboard import Dashboard

        catalog_dashboard = get_dashboard(db, catalog_name, schema_name, dashboard_name)
        actor = _current_actor(user)

        if body.comment is not None:
            catalog_dashboard.comment = body.comment
        if body.owner is not None:
            catalog_dashboard.owner = body.owner

        if body.name is not None and body.name != catalog_dashboard.name:
            # Check name uniqueness in target schema
            existing = db.query(UnifiedCatalogDashboard).filter(
                UnifiedCatalogDashboard.catalog_name == catalog_name,
                UnifiedCatalogDashboard.schema_name == schema_name,
                UnifiedCatalogDashboard.name == body.name
            ).first()
            if existing:
                raise ValueError(f"Dashboard '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")
            catalog_dashboard.name = body.name

            # Also rename in system dashboard table if it exists
            if catalog_dashboard.dashboard_id:
                system_dash = db.query(Dashboard).filter(Dashboard.id == catalog_dashboard.dashboard_id).first()
                if system_dash:
                    system_dash.name = body.name

        catalog_dashboard.updated_by = actor
        db.commit()
        db.refresh(catalog_dashboard)

        # Re-enqueue embedding whenever name or comment changes
        if body.name is not None or body.comment is not None:
            try:
                self.search_index.enqueue(
                    db,
                    object_type="dashboard",
                    source_object_id=catalog_dashboard.id,
                    catalog_name=catalog_dashboard.catalog_name,
                    schema_name=catalog_dashboard.schema_name,
                    object_name=catalog_dashboard.name,
                    description=catalog_dashboard.comment,
                )
                db.commit()
            except Exception as _idx_err:
                import logging as _log
                self.log.warning("Failed to re-enqueue embedding for dashboard %s: %s", catalog_dashboard.name, _idx_err)

        return catalog_dashboard

def update_dashboard(db: Session, catalog_name: str, schema_name: str, dashboard_name: str, body: DashboardUpdate, user: dict) -> UnifiedCatalogDashboard:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = UpdateDashboard(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, dashboard_name, body, user)
