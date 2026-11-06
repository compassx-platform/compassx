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

def _ensure_catalog_by_name(db: Session, name: str, actor: str) -> UnifiedCatalog:
    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == name).first()
    if catalog:
        return catalog
    catalog = UnifiedCatalog(name=name, created_by=actor)
    db.add(catalog)
    db.commit()
    db.refresh(catalog)
    return catalog

def _ensure_schema_by_name(db: Session, catalog: UnifiedCatalog, name: str, actor: str) -> UnifiedCatalogSchema:
    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == name)
        .first()
    )
    if schema:
        return schema
    schema = UnifiedCatalogSchema(catalog_id=catalog.id, name=name, created_by=actor)
    db.add(schema)
    db.commit()
    db.refresh(schema)
    return schema

