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

class DeleteTable:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    def execute(self, db: Session, catalog_name: str, schema_name: str, table_name: str) -> None:
        """Soft-delete an Iceberg table by removing its catalog metadata entry.

        The actual physical data and metadata files in blob storage are preserved.
        Only Iceberg tables can be deleted from the catalog.
        """
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")
        schema = db.query(UnifiedCatalogSchema).filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name
        ).first()
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")
        table = db.query(UnifiedCatalogTable).filter(
            UnifiedCatalogTable.schema_id == schema.id,
            UnifiedCatalogTable.name == table_name
        ).first()
        if not table:
            raise ValueError(f"Table '{table_name}' not found in '{catalog_name}.{schema_name}'.")

        if table.table_type != CatalogTableType.ICEBERG:
            table_type_val = table.table_type.value if hasattr(table.table_type, 'value') else str(table.table_type)
            raise ValueError(f"Only Iceberg tables can be deleted from the catalog. Table '{table_name}' is of type '{table_type_val}'.")

        # Clean up search asset index if exists
        try:
            from app.catalog.search_models import CatalogSearchAsset
            db.query(CatalogSearchAsset).filter(
                CatalogSearchAsset.source_object_id == table.id
            ).delete(synchronize_session=False)
        except Exception:
            pass

        # Clean up lineage edges referencing this table
        db.query(UnifiedCatalogLineage).filter(
            (UnifiedCatalogLineage.source_table_id == table.id) | (UnifiedCatalogLineage.target_table_id == table.id)
        ).delete(synchronize_session=False)

        db.delete(table)
        db.commit()

def delete_table(db: Session, catalog_name: str, schema_name: str, table_name: str) -> None:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = DeleteTable(search_index(), catalog_log(), postgres_reader())
    return action.execute(db, catalog_name, schema_name, table_name)
