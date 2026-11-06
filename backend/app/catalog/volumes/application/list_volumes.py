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

class ListVolumes:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog: str | None=None, schema_name: str | None=None) -> list[UnifiedCatalogVolume]:
        from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogVolume
        query = db.query(UnifiedCatalogVolume)

        if catalog or schema_name:
            query = query.join(UnifiedCatalogVolume.schema).join(UnifiedCatalogSchema.catalog)
            if catalog:
                query = query.filter(UnifiedCatalog.name == catalog)
            if schema_name:
                query = query.filter(UnifiedCatalogSchema.name == schema_name)

        return query.order_by(UnifiedCatalogVolume.name).all()

def list_volumes(db: Session, catalog: str | None=None, schema_name: str | None=None) -> list[UnifiedCatalogVolume]:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = ListVolumes(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog, schema_name)
