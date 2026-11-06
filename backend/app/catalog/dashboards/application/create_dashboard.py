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

class CreateDashboard:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, body: DashboardCreate, user: dict) -> UnifiedCatalogDashboard:
        from app.catalog.runtime import _current_actor
        from uuid import uuid4
        from app.dashboards.models.dashboard import Dashboard

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
        existing = db.query(UnifiedCatalogDashboard).filter(
            UnifiedCatalogDashboard.catalog_name == catalog_name,
            UnifiedCatalogDashboard.schema_name == schema_name,
            UnifiedCatalogDashboard.name == body.name
        ).first()
        if existing:
            raise ValueError(f"Dashboard '{body.name}' already exists in schema '{catalog_name}.{schema_name}'.")

        actor = _current_actor(user)

        # Create both the dashboard JSON and the catalog metadata in the account DB.
        dash_id = str(uuid4())
        first_page_id = str(uuid4())
        dashboard_record = Dashboard(
            id=dash_id,
            name=body.name,
            folder_id=None,
            permission_mode="individual",
            is_draft=True,
            pages=[{
                "id": first_page_id,
                "dashboardId": dash_id,
                "name": "Page 1",
                "order": 0,
                "layout": [],
            }],
            widgets=[],
            datasets=[],
            settings=None,
            created_by=actor,
        )
        catalog_dashboard = UnifiedCatalogDashboard(
            schema_id=schema.id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            name=body.name,
            dashboard_id=dash_id,
            owner=actor,
            comment=body.comment,
            created_by=actor,
            updated_by=actor,
        )
        db.add(dashboard_record)
        db.add(catalog_dashboard)
        db.commit()
        db.refresh(catalog_dashboard)

        # Enqueue embedding for semantic search
        try:
            self.search_index.enqueue(
                db,
                object_type="dashboard",
                source_object_id=catalog_dashboard.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=catalog_dashboard.name,
                description=catalog_dashboard.comment,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            self.log.warning("Failed to enqueue embedding for dashboard %s: %s", catalog_dashboard.name, _idx_err)

        return catalog_dashboard

async def create_dashboard(db: Session, catalog_name: str, schema_name: str, body: DashboardCreate, user: dict) -> UnifiedCatalogDashboard:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateDashboard(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, body, user)
