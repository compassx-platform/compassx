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

class GetSampleData:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, fqn: str, limit: int=100) -> SampleDataRead:
        from app.catalog.runtime import _parse_fqn, _connect_record, _get_connection
        catalog_name, schema_name, table_name = _parse_fqn(fqn)
        cat_model = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()

        # Postgres catalog — query live
        if cat_model and cat_model.catalog_type == "postgres" and cat_model.connection_id and cat_model.database_name:
            conn = _connect_record(_get_connection(db, cat_model.connection_id), cat_model.database_name)
            try:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT %s',
                    (limit,),
                )
                rows_raw = cur.fetchall()
                if not rows_raw:
                    return SampleDataRead(columns=[], rows=[], row_count=0)
                columns = list(rows_raw[0].keys())
                rows = [[str(v) if v is not None else None for v in row.values()] for row in rows_raw]
                return SampleDataRead(columns=columns, rows=rows, row_count=len(rows))
            finally:
                conn.close()

        # Registered table (either postgres_native or iceberg)
        table = (
            db.query(UnifiedCatalogTable)
            .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
            .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
            .filter(
                UnifiedCatalog.name == catalog_name,
                UnifiedCatalogSchema.name == schema_name,
                UnifiedCatalogTable.name == table_name,
            )
            .first()
        )
        if not table:
            raise ValueError(f"Table '{fqn}' not found")

        if table.table_type == CatalogTableType.POSTGRES_NATIVE and table.connection_id:
            conn = _connect_record(_get_connection(db, table.connection_id), table.source_database)
            try:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(
                    f'SELECT * FROM "{table.pg_schema}"."{table.pg_table}" LIMIT %s',
                    (limit,),
                )
                rows_raw = cur.fetchall()
                if not rows_raw:
                    return SampleDataRead(columns=[], rows=[], row_count=0)
                columns = list(rows_raw[0].keys())
                rows = [[str(v) if v is not None else None for v in row.values()] for row in rows_raw]
                return SampleDataRead(columns=columns, rows=rows, row_count=len(rows))
            finally:
                conn.close()

        if table.table_type == CatalogTableType.ICEBERG:
            sch = table.schema
            cat_name = sch.catalog.name if sch and sch.catalog else catalog_name
            ctx = resolve_catalog_storage(db, cat_name, sch.name if sch else schema_name)
            if not ctx:
                raise ValueError("No storage backend configured for this schema")

            data_file = table.properties.get("data_file")
            if not data_file:
                table_path_rel = ctx.rel_path(f"tables/{table.name}")
                files = await ctx.backend.list_files(f"{table_path_rel}/data/")
                data_files = [f for f in files if f.file_name != "_keep"]
                if data_files:
                    data_file = data_files[0].file_name

            if not data_file:
                return SampleDataRead(columns=[c.name for c in table.columns], rows=[], row_count=0)

            table_path_rel = ctx.rel_path(f"tables/{table.name}")
            file_path = f"{table_path_rel}/data/{data_file}"

            try:
                file_bytes = await ctx.backend.read_bytes(file_path)
                import io
                import pandas as pd
                import numpy as np
                ext = data_file.split('.')[-1].lower()
                if ext == 'csv':
                    df = pd.read_csv(io.BytesIO(file_bytes))
                elif ext in ('xls', 'xlsx'):
                    df = pd.read_excel(io.BytesIO(file_bytes))
                elif ext in ('json', 'jsonl'):
                    df = pd.read_json(io.BytesIO(file_bytes), lines=(ext == 'jsonl' or b'\n' in file_bytes))
                elif ext == 'parquet':
                    df = pd.read_parquet(io.BytesIO(file_bytes))
                else:
                    df = pd.read_csv(io.BytesIO(file_bytes))

                df_head = df.head(limit)
                columns = list(df_head.columns)
                rows = []
                for _, row in df_head.iterrows():
                    row_vals = []
                    for col in columns:
                        val = row.get(col)
                        if pd.isna(val) or val is None or (isinstance(val, float) and np.isnan(val)):
                            row_vals.append(None)
                        else:
                            row_vals.append(str(val))
                    rows.append(row_vals)
                return SampleDataRead(columns=columns, rows=rows, row_count=len(rows))
            except Exception as e:
                print(f"Error reading sample data from Iceberg blob: {e}")
                return SampleDataRead(columns=[c.name for c in table.columns], rows=[], row_count=0)

        raise ValueError(f"Sample data not supported for table type '{table.table_type}'")

async def get_sample_data(db: Session, fqn: str, limit: int=100) -> SampleDataRead:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = GetSampleData(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, fqn, limit)
