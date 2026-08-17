"""
iceberg_loader.py — Downloads Iceberg table data from blob storage and returns
pandas DataFrames for in-memory DuckDB query execution.

This module is the production-grade alternative to DuckDB's Azure/S3 extensions,
which have fragile metadata resolution. Instead, we use our own storage abstraction
(which is already tested and production-proven) to fetch data, parse it, and hand
a fully-typed DataFrame to DuckDB's Python API.

Architecture:
    executor.py
        └─ build_duckdb_iceberg_preloads(db)  ← async, runs in event loop
               └─ StorageBackend.read_bytes()  ← our abstraction (Azure / S3 / MinIO)
               └─ parse bytes → pd.DataFrame
    duckdb_adapter.py
        └─ conn.register(name, df)  ← zero-dependency, in-process
        └─ CREATE VIEW catalog.schema.table AS SELECT * FROM _ref_
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.catalog.models import CatalogTableType, UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogTable
from app.storage.db_models import StorageBackend
from app.storage.service import storage_service

logger = logging.getLogger(__name__)


@dataclass
class PreloadedTable:
    catalog: str
    schema: str
    table: str
    df: pd.DataFrame
    # Internal DuckDB registration name (no dots, no special chars)
    internal_name: str


def _backend_base(backend: StorageBackend) -> str:
    if backend.provider == "azure":
        return (backend.azure_base_path or "compassx/").rstrip("/")
    return (backend.s3_base_path or "compassx/").rstrip("/")


def _table_dir_rel(table: UnifiedCatalogTable, base: str) -> str:
    """Return the path to the table directory, relative to the storage backend root."""
    def strip(path: str) -> str:
        path = path.strip("/")
        pfx = base.strip("/")
        if pfx and path.startswith(pfx + "/"):
            return path[len(pfx) + 1:]
        return path

    if table.storage_location:
        return strip(table.storage_location)
    if table.metadata_location:
        loc = table.metadata_location.strip("/")
        if "/metadata/" in loc:
            loc = loc.split("/metadata/")[0]
        return strip(loc)
    raise ValueError(f"Table '{table.name}' has no storage_location or metadata_location")


def _parse_bytes(data: bytes, fmt: str, filename: str) -> pd.DataFrame:
    """Parse raw bytes into a DataFrame based on file format."""
    buf = io.BytesIO(data)
    fmt = (fmt or "").lower().strip()

    if fmt == "parquet" or filename.endswith(".parquet"):
        return pd.read_parquet(buf, engine="pyarrow")
    if fmt in ("csv", "tsv") or filename.endswith((".csv", ".tsv")):
        sep = "\t" if fmt == "tsv" or filename.endswith(".tsv") else ","
        return pd.read_csv(buf, sep=sep)
    if fmt in ("json",) or filename.endswith(".json"):
        return pd.read_json(buf)
    if fmt in ("jsonl", "ndjson") or filename.endswith((".jsonl", ".ndjson")):
        return pd.read_json(buf, lines=True)
    if fmt in ("xlsx", "xls") or filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(buf)

    # Unknown format — try parquet first, then CSV
    try:
        return pd.read_parquet(io.BytesIO(data), engine="pyarrow")
    except Exception:
        return pd.read_csv(io.BytesIO(data))


async def _resolve_data_file(
    backend,
    tdir: str,
    props: dict,
    file_format: str,
    table_name: str,
) -> tuple[str, bytes]:
    """
    Find and download the data file for an Iceberg table.

    Priority:
    1. props['data_file'] — explicit filename recorded at creation time
    2. Glob data/ directory for any supported file
    3. Try common naming patterns

    Returns (filename, bytes).
    """
    # 1. Explicit data_file from properties
    if props.get("data_file"):
        path = f"{tdir.rstrip('/')}/data/{props['data_file']}"
        try:
            data = await backend.read_bytes(path)
            return props["data_file"], data
        except Exception as exc:
            logger.warning("Explicit data_file '%s' not found: %s", path, exc)

    # 2. List the data/ directory and pick the first supported file
    data_dir = f"{tdir.rstrip('/')}/data"
    try:
        files = await backend.list_files(data_dir)
        supported_exts = (".parquet", ".csv", ".tsv", ".json", ".jsonl", ".xlsx", ".xls")
        candidates = [
            f for f in files
            if any(f.file_path.lower().endswith(ext) for ext in supported_exts)
        ]
        if candidates:
            # Prefer parquet, then csv, then others
            candidates.sort(key=lambda f: (
                0 if f.file_path.endswith(".parquet") else
                1 if f.file_path.endswith(".csv") else 2
            ))
            best = candidates[0]
            # file_path is the full relative path from backend root
            data = await backend.read_bytes(best.file_path)
            filename = best.file_path.split("/")[-1]
            return filename, data
    except Exception as exc:
        logger.warning("Could not list data dir '%s': %s", data_dir, exc)

    # 3. Common naming fallbacks
    ext = file_format if file_format in ("parquet", "csv", "json", "jsonl") else "parquet"
    fallbacks = [
        f"{tdir.rstrip('/')}/data/{table_name}.{ext}",
        f"{tdir.rstrip('/')}/data/{table_name}.parquet",
        f"{tdir.rstrip('/')}/data/{table_name}.csv",
        f"{tdir.rstrip('/')}/data/data.parquet",
        f"{tdir.rstrip('/')}/data/data.csv",
    ]
    for path in fallbacks:
        try:
            data = await backend.read_bytes(path)
            return path.split("/")[-1], data
        except Exception:
            continue

    raise FileNotFoundError(
        f"No data file found for table '{table_name}' in '{data_dir}'. "
        f"Tried props['data_file']={props.get('data_file')!r}, directory listing, and fallback patterns."
    )


async def build_duckdb_iceberg_preloads(db: Session) -> list[PreloadedTable]:
    """
    Download all Iceberg table data files from blob storage and return as typed DataFrames.

    This function is the core of the production-grade query path: instead of relying on
    DuckDB's Azure/S3 extensions (which have known issues), we use our own storage backend
    abstraction to fetch data and inject it directly into DuckDB's Python API.

    Called once per query execution. Results are not cached — the query cache in
    result_cache.py handles repeated identical queries.
    """
    iceberg_tables: list[UnifiedCatalogTable] = (
        db.query(UnifiedCatalogTable)
        .join(UnifiedCatalogSchema, UnifiedCatalogTable.schema_id == UnifiedCatalogSchema.id)
        .join(UnifiedCatalog, UnifiedCatalogSchema.catalog_id == UnifiedCatalog.id)
        .options(
            joinedload(UnifiedCatalogTable.schema).joinedload(UnifiedCatalogSchema.catalog)
        )
        .filter(UnifiedCatalogTable.table_type == CatalogTableType.ICEBERG)
        .order_by(UnifiedCatalog.name, UnifiedCatalogSchema.name, UnifiedCatalogTable.name)
        .all()
    )

    preloads: list[PreloadedTable] = []

    for table in iceberg_tables:
        schema = table.schema
        catalog = schema.catalog

        if not schema.storage_backend_id:
            logger.warning(
                "Iceberg table '%s.%s.%s' has no storage backend — skipping",
                catalog.name, schema.name, table.name,
            )
            continue

        backend_row: StorageBackend | None = db.get(StorageBackend, schema.storage_backend_id)
        if not backend_row:
            logger.warning(
                "Storage backend for table '%s.%s.%s' not found — skipping",
                catalog.name, schema.name, table.name,
            )
            continue

        base = _backend_base(backend_row)

        try:
            tdir = _table_dir_rel(table, base)
        except ValueError as exc:
            logger.warning("Cannot resolve table dir for '%s.%s.%s': %s", catalog.name, schema.name, table.name, exc)
            continue

        props: dict[str, Any] = table.properties or {}
        file_format: str = table.file_format or props.get("file_format") or "parquet"

        try:
            backend = storage_service.get_backend(db, backend_row.name)
            filename, data_bytes = await _resolve_data_file(
                backend=backend,
                tdir=tdir,
                props=props,
                file_format=file_format,
                table_name=table.name,
            )
        except Exception as exc:
            logger.warning(
                "Failed to download data for '%s.%s.%s': %s",
                catalog.name, schema.name, table.name, exc,
            )
            continue

        try:
            df = _parse_bytes(data_bytes, file_format, filename)
        except Exception as exc:
            logger.warning(
                "Failed to parse data for '%s.%s.%s' (file=%s fmt=%s): %s",
                catalog.name, schema.name, table.name, filename, file_format, exc,
            )
            continue

        # Sanitise: replace NaN/NaT with None for DuckDB compatibility
        df = df.where(pd.notna(df), other=None)

        internal_name = (
            f"_compassx_"
            + catalog.name.replace("-", "_").replace(".", "_")
            + "_"
            + schema.name.replace("-", "_").replace(".", "_")
            + "_"
            + table.name.replace("-", "_").replace(".", "_")
        )

        preloads.append(PreloadedTable(
            catalog=catalog.name,
            schema=schema.name,
            table=table.name,
            df=df,
            internal_name=internal_name,
        ))
        logger.info(
            "Preloaded Iceberg table '%s.%s.%s' — %d rows × %d cols from '%s'",
            catalog.name, schema.name, table.name, len(df), len(df.columns), filename,
        )

    return preloads
