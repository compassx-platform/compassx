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

class GetLineage:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, fqn: str) -> LineageGraphRead:
        from app.catalog.runtime import _parse_fqn, _get_table_model
        catalog_name, schema_name, table_name = _parse_fqn(fqn)
        cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if cat_model and cat_model.catalog_type == "postgres":
            return LineageGraphRead(upstream=[], downstream=[])

        table = _get_table_model(db, fqn)
        upstream_rows = (
            db.query(UnifiedCatalogLineage, UnifiedCatalogTable, UnifiedCatalogSchema, UnifiedCatalog)
            .join(UnifiedCatalogTable, UnifiedCatalogLineage.source_table_id == UnifiedCatalogTable.id)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
            .filter(UnifiedCatalogLineage.target_table_id == table.id)
            .all()
        )
        downstream_rows = (
            db.query(UnifiedCatalogLineage, UnifiedCatalogTable, UnifiedCatalogSchema, UnifiedCatalog)
            .join(UnifiedCatalogTable, UnifiedCatalogLineage.target_table_id == UnifiedCatalogTable.id)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
            .filter(UnifiedCatalogLineage.source_table_id == table.id)
            .all()
        )
        return LineageGraphRead(
            upstream=[
                LineageEdgeRead(
                    source_fqn=f"{catalog.name}.{schema.name}.{related.name}",
                    target_fqn=fqn,
                    transformation=edge.transformation,
                    created_at=edge.created_at,
                )
                for edge, related, schema, catalog in upstream_rows
            ],
            downstream=[
                LineageEdgeRead(
                    source_fqn=fqn,
                    target_fqn=f"{catalog.name}.{schema.name}.{related.name}",
                    transformation=edge.transformation,
                    created_at=edge.created_at,
                )
                for edge, related, schema, catalog in downstream_rows
            ],
        )

def get_lineage(db: Session, fqn: str) -> LineageGraphRead:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = GetLineage(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, fqn)
