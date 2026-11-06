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

class CreateTableFromFile:
    def __init__(self, search_index, log, postgres=None):
        self.search_index = search_index
        self.log = log
        self.postgres = postgres

    async def execute(self, db: Session, catalog_name: str, schema_name: str, table_name: str, description: str | None, columns: list[dict], file_name: str, file_bytes: bytes, user: dict) -> UnifiedCatalogTable:
        from app.catalog.runtime import _current_actor, _get_connection, _connect_record
        import io
        import pandas as pd
        import numpy as np

        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            raise ValueError(f"Catalog '{catalog_name}' not found.")

        schema = (
            db.query(UnifiedCatalogSchema)
            .filter(UnifiedCatalogSchema.catalog_id == catalog.id, UnifiedCatalogSchema.name == schema_name)
            .first()
        )
        if not schema:
            raise ValueError(f"Schema '{schema_name}' not found in catalog '{catalog_name}'.")

        existing = (
            db.query(UnifiedCatalogTable)
            .filter(UnifiedCatalogTable.schema_id == schema.id, UnifiedCatalogTable.name == table_name)
            .first()
        )
        if existing:
            raise ValueError(f"Table '{table_name}' already exists in schema '{schema_name}'.")

        ext = file_name.split('.')[-1].lower() if file_name else 'csv'
        try:
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
        except Exception as e:
            raise ValueError(f"Failed to parse uploaded file: {e}")

        actor = _current_actor(user)

        if catalog.catalog_type == "postgres" and catalog.connection_id:
            # 1. CREATE TABLE in PostgreSQL database
            connection = _get_connection(db, catalog.connection_id)

            cols_sql = []
            for c in columns:
                col_name = c["name"]
                dt = c.get("data_type", "string").lower()
                null_str = "NULL" if c.get("nullable", True) else "NOT NULL"

                if dt in ("int", "int32", "integer"):
                    pg_type = "INTEGER"
                elif dt in ("long", "int64", "bigint"):
                    pg_type = "BIGINT"
                elif dt in ("double", "float64", "float", "real"):
                    pg_type = "DOUBLE PRECISION"
                elif dt in ("bool", "boolean"):
                    pg_type = "BOOLEAN"
                elif dt in ("timestamp", "timestamptz", "datetime"):
                    pg_type = "TIMESTAMP WITH TIME ZONE"
                elif dt == "date":
                    pg_type = "DATE"
                elif dt == "decimal":
                    pg_type = "NUMERIC"
                elif dt == "json":
                    pg_type = "JSONB"
                elif dt == "binary":
                    pg_type = "BYTEA"
                else:
                    pg_type = "TEXT"

                cols_sql.append(f'"{col_name}" {pg_type} {null_str}')

            create_sql = f'CREATE TABLE "{schema_name}"."{table_name}" (\n  ' + ",\n  ".join(cols_sql) + "\n)"

            conn = _connect_record(connection, catalog.database_name)
            try:
                cur = conn.cursor()
                cur.execute(create_sql)

                # Insert values
                placeholders = ", ".join(["%s"] * len(columns))
                col_names_str = ", ".join([f'"{c["name"]}"' for c in columns])
                insert_sql = f'INSERT INTO "{schema_name}"."{table_name}" ({col_names_str}) VALUES ({placeholders})'

                rows_to_insert = []
                for _, row in df.iterrows():
                    row_vals = []
                    for col_info in columns:
                        name = col_info["name"]
                        val = row.get(name)
                        if pd.isna(val) or val is None or (isinstance(val, float) and np.isnan(val)):
                            row_vals.append(None)
                        else:
                            dt = col_info.get("data_type", "string").lower()
                            if dt in ("int", "int32", "integer", "long", "int64", "bigint"):
                                try:
                                    row_vals.append(int(val))
                                except:
                                    row_vals.append(None)
                            elif dt in ("double", "float64", "float", "real", "decimal"):
                                try:
                                    row_vals.append(float(val))
                                except:
                                    row_vals.append(None)
                            elif dt in ("bool", "boolean"):
                                if isinstance(val, str):
                                    row_vals.append(val.lower() in ("true", "1", "yes", "t"))
                                else:
                                    row_vals.append(bool(val))
                            else:
                                row_vals.append(str(val))
                    rows_to_insert.append(row_vals)

                if rows_to_insert:
                    cur.executemany(insert_sql, rows_to_insert)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise ValueError(f"Postgres storage failed: {e}")
            finally:
                conn.close()

            # 2. Register in metadata
            table = UnifiedCatalogTable(
                schema_id=schema.id,
                name=table_name,
                table_type=CatalogTableType.POSTGRES_NATIVE,
                connection_id=catalog.connection_id,
                source_database=catalog.database_name,
                pg_schema=schema_name,
                pg_table=table_name,
                description=description,
                owner=actor,
                created_by=actor
            )
            db.add(table)
            db.commit()
            db.refresh(table)

        elif catalog.catalog_type in ("iceberg", None, ""):
            # ── Iceberg storage: always write Parquet, never raw CSV/JSON ─────────
            from app.catalog.iceberg_manager import IcebergManager

            ctx_upload = resolve_catalog_storage(db, catalog_name, schema_name)
            if not ctx_upload:
                raise ValueError(
                    f"No storage backend configured for schema '{schema_name}' or catalog '{catalog_name}'. "
                    "Bind a blob storage backend to the catalog or schema first."
                )

            table_path_abs = ctx_upload.abs_path(f"tables/{table_name}")
            table_path_rel = ctx_upload.rel_path(f"tables/{table_name}")

            mgr = IcebergManager(ctx_upload.backend)

            if await mgr.table_exists(table_path_rel):
                raise ValueError(
                    f"Iceberg metadata already exists at {table_path_abs}. "
                    "The table name is already in use on blob storage."
                )

            # ── Convert data to Parquet (native Iceberg storage format) ──────────
            # Apply user-specified column types before writing
            import io as _io
            for col_info in columns:
                col_name = col_info["name"]
                dt = col_info.get("data_type", "string").lower()
                if col_name not in df.columns:
                    continue
                try:
                    if dt in ("int", "int32", "integer"):
                        df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype("Int32")
                    elif dt in ("long", "int64", "bigint"):
                        df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype("Int64")
                    elif dt in ("double", "float64", "float", "real", "decimal"):
                        df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype("float64")
                    elif dt in ("bool", "boolean"):
                        df[col_name] = df[col_name].map(
                            lambda v: True if str(v).lower() in ("true", "1", "yes", "t") else False
                            if str(v).lower() in ("false", "0", "no", "f") else None
                        )
                    elif dt == "timestamp":
                        df[col_name] = pd.to_datetime(df[col_name], errors="coerce", utc=True)
                    elif dt == "date":
                        df[col_name] = pd.to_datetime(df[col_name], errors="coerce").dt.date
                except Exception:
                    pass  # Keep column as-is if cast fails

            parquet_buf = _io.BytesIO()
            df.to_parquet(parquet_buf, index=False, engine="pyarrow", row_group_size=50_000)
            parquet_bytes = parquet_buf.getvalue()
            parquet_file_name = f"{table_name}.parquet"
            storage_format = "parquet"
            # ─────────────────────────────────────────────────────────────────────

            # Write Parquet file to the storage backend under data/
            await ctx_upload.backend.write_bytes(
                path=f"{table_path_rel}/data/{parquet_file_name}",
                data=parquet_bytes,
                content_type="application/octet-stream"
            )

            metadata_location_rel = await mgr.create_table(
                table_path=table_path_rel,
                table_name=table_name,
                columns=columns,
                properties={"file_format": storage_format, "data_file": parquet_file_name}
            )
            metadata_location_abs = f"{ctx_upload.backend_base}{metadata_location_rel}"

            table = UnifiedCatalogTable(
                schema_id=schema.id,
                name=table_name,
                table_type=CatalogTableType.ICEBERG,
                metadata_location=metadata_location_abs,
                storage_location=table_path_abs,
                file_format=storage_format,
                description=description,
                owner=actor,
                created_by=actor,
                properties={"data_file": parquet_file_name, "file_format": storage_format, "source_file": file_name}
            )
            db.add(table)
            db.commit()
            db.refresh(table)

        else:
            raise ValueError(
                f"Unsupported catalog type '{catalog.catalog_type}'. "
                "File-based table creation is supported for 'postgres' and 'iceberg' catalog types only."
            )

        # Common: Register columns
        for idx, col in enumerate(columns):
            db.add(
                UnifiedCatalogColumn(
                    table_id=table.id,
                    name=col["name"],
                    data_type=col.get("data_type", "string"),
                    nullable=col.get("nullable", True),
                    description=col.get("description"),
                    ordinal=idx + 1
                )
            )
        db.commit()
        db.refresh(table)

        # Enqueue embedding for semantic search
        try:
            col_summary = ", ".join(f"{c['name']} ({c.get('data_type', 'string')})" for c in columns)
            self.search_index.enqueue(
                db,
                object_type="table",
                source_object_id=table.id,
                catalog_name=catalog_name,
                schema_name=schema_name,
                object_name=table.name,
                description=table.description,
                content_summary=col_summary,
            )
            db.commit()
        except Exception as _idx_err:
            import logging as _log
            self.log.warning("Failed to enqueue embedding for table %s: %s", table.name, _idx_err)

        return table

async def create_table_from_file(db: Session, catalog_name: str, schema_name: str, table_name: str, description: str | None, columns: list[dict], file_name: str, file_bytes: bytes, user: dict) -> UnifiedCatalogTable:
    from app.catalog.composition import catalog_log, postgres_reader, search_index
    action = CreateTableFromFile(search_index(), catalog_log(), postgres_reader())
    return await action.execute(db, catalog_name, schema_name, table_name, description, columns, file_name, file_bytes, user)
