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

def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.new_event_loop().run_until_complete(coro))
            return future.result()
    else:
        return loop.run_until_complete(coro)

def _resolve_notebook_ctx(db: Session, schema) -> 'StorageContext | None':
    """Resolve StorageContext for a notebook's schema, walking up to catalog if needed."""
    return resolve_catalog_storage_by_schema_id(db, schema.id)

async def _write_notebook_content(db: Session, schema, blob_path: str, content: dict) -> None:
    import json
    ctx = _resolve_notebook_ctx(db, schema)
    content_str = json.dumps(content, indent=2)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        await ctx.backend.write_bytes(key, content_str.encode("utf-8"), "application/x-ipynb+json")
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        fs.write_text(_NOTEBOOKS_BUCKET, key, content_str)

async def _read_notebook_content(db: Session, schema, blob_path: str) -> dict:
    import json
    ctx = _resolve_notebook_ctx(db, schema)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        data = await ctx.backend.read_bytes(key)
        return json.loads(data.decode("utf-8"))
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        return json.loads(fs.read_text(_NOTEBOOKS_BUCKET, key))

async def _delete_notebook_file(db: Session, schema, blob_path: str) -> None:
    ctx = _resolve_notebook_ctx(db, schema)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        try:
            if await ctx.backend.exists(key):
                await ctx.backend.delete(key)
        except Exception as e:
            import logging
            logging.getLogger("app.catalog.service").warning("Failed to delete storage notebook key %s: %s", key, e)
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        try:
            if fs.exists(_NOTEBOOKS_BUCKET, key):
                fs.delete(_NOTEBOOKS_BUCKET, key)
        except Exception as e:
            import logging
            logging.getLogger("app.catalog.service").warning("Failed to delete notebook key %s: %s", key, e)

async def _notebook_exists(db: Session, schema, blob_path: str) -> bool:
    ctx = _resolve_notebook_ctx(db, schema)
    if ctx:
        key = ctx.rel_path(f"notebooks/{blob_path}")
        return await ctx.backend.exists(key)
    else:
        from app.notebooks.routes.notebook_routes import _NOTEBOOKS_BUCKET, _safe_key
        from services.storage.fs import get_fs
        key = _safe_key(blob_path)
        fs = get_fs()
        return fs.exists(_NOTEBOOKS_BUCKET, key)

