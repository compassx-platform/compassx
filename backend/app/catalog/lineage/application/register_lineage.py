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

class RegisterLineage:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, data: LineageEdgeCreate, user: dict | None) -> None:
        from app.catalog.runtime import _current_actor, _get_table_model
        actor = _current_actor(user)
        source = _get_table_model(db, data.source_fqn)
        target = _get_table_model(db, data.target_fqn)
        edge = (
            db.query(UnifiedCatalogLineage)
            .filter(
                UnifiedCatalogLineage.source_table_id == source.id,
                UnifiedCatalogLineage.target_table_id == target.id,
            )
            .first()
        )
        if edge is None:
            edge = UnifiedCatalogLineage(source_table_id=source.id, target_table_id=target.id, created_by=actor)
            db.add(edge)
        edge.transformation = data.transformation
        db.commit()

def register_lineage(db: Session, data: LineageEdgeCreate, user: dict | None) -> None:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = RegisterLineage(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, data, user)
