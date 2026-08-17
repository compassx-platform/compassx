"""Catalog-backed resolution of notebook assets used by Jobs."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import or_

from app.catalog.models import UnifiedCatalogNotebook, UnifiedCatalogSchema
from app.catalog.storage_context import resolve_catalog_storage_by_schema_id
from app.database import AccountSessionLocal
from services.storage.config import storage_settings
from services.storage.fs import get_fs


class NotebookAssetNotFound(ValueError):
    pass


@dataclass(frozen=True)
class NotebookAsset:
    notebook_id: str
    catalog_name: str
    schema_name: str
    name: str
    blob_path: str
    storage_location: str


class NotebookAssetResolver(ABC):
    """Storage-provider-independent notebook lookup port."""

    @abstractmethod
    def resolve(self, target_ref: str, workspace_id: str | None = None) -> NotebookAsset: ...

    @abstractmethod
    def exists(self, target_ref: str, workspace_id: str | None = None) -> bool: ...

    @abstractmethod
    async def read(self, target_ref: str, workspace_id: str | None = None) -> bytes: ...


def normalize_target_ref(value: str) -> str:
    return value.strip().lstrip("/").replace("\\", "/")


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coro)).result()


async def _close_backend(backend) -> None:
    """Release provider clients created for a short-lived catalog lookup."""
    client = getattr(backend, "_client", None)
    if client is not None and hasattr(client, "close"):
        await client.close()


async def _exists_and_close(backend, key: str) -> bool:
    try:
        return await backend.exists(key)
    finally:
        await _close_backend(backend)


class CatalogNotebookAssetResolver(NotebookAssetResolver):
    """Resolve immutable notebook blob IDs through catalog storage metadata."""

    @staticmethod
    def _record(db, target_ref: str) -> UnifiedCatalogNotebook:
        target = normalize_target_ref(target_ref)
        if target.startswith("catalog-notebook://"):
            target = target.removeprefix("catalog-notebook://")
        matches = db.query(UnifiedCatalogNotebook).filter(
            or_(
                UnifiedCatalogNotebook.id == target,
                UnifiedCatalogNotebook.blob_path == target,
                UnifiedCatalogNotebook.full_name == target,
                UnifiedCatalogNotebook.name == target,
            )
        ).all()
        if not matches:
            raise NotebookAssetNotFound(f"Notebook is not registered in the catalog: {target_ref}")
        if len(matches) > 1:
            raise NotebookAssetNotFound(
                f"Notebook reference is ambiguous; use its catalog full name or ID: {target_ref}"
            )
        return matches[0]

    def resolve(self, target_ref: str, workspace_id: str | None = None) -> NotebookAsset:
        db = AccountSessionLocal()
        try:
            notebook = self._record(db, target_ref)
            ctx = resolve_catalog_storage_by_schema_id(
                db,
                notebook.schema_id,
                workspace_id=workspace_id,
            )
            location = (
                ctx.abs_path(f"notebooks/{notebook.blob_path}")
                if ctx
                else storage_settings.notebooks_object_name(notebook.blob_path)
            )
            return NotebookAsset(
                notebook_id=notebook.id,
                catalog_name=notebook.catalog_name,
                schema_name=notebook.schema_name,
                name=notebook.name,
                blob_path=notebook.blob_path,
                storage_location=location,
            )
        finally:
            db.close()

    def exists(self, target_ref: str, workspace_id: str | None = None) -> bool:
        db = AccountSessionLocal()
        try:
            notebook = self._record(db, target_ref)
            ctx = resolve_catalog_storage_by_schema_id(
                db,
                notebook.schema_id,
                workspace_id=workspace_id,
            )
            if ctx:
                key = ctx.rel_path(f"notebooks/{notebook.blob_path}")
                return bool(_run(_exists_and_close(ctx.backend, key)))
            key = storage_settings.notebooks_object_name(notebook.blob_path)
            return get_fs().exists(storage_settings.STORAGE_NOTEBOOKS_BUCKET, key)
        finally:
            db.close()

    async def read(self, target_ref: str, workspace_id: str | None = None) -> bytes:
        db = AccountSessionLocal()
        try:
            notebook = self._record(db, target_ref)
            schema = db.query(UnifiedCatalogSchema).filter(
                UnifiedCatalogSchema.id == notebook.schema_id
            ).first()
            if schema is None:
                raise NotebookAssetNotFound("Notebook catalog schema no longer exists")
            ctx = resolve_catalog_storage_by_schema_id(
                db,
                schema.id,
                workspace_id=workspace_id,
            )
            if ctx:
                key = ctx.rel_path(f"notebooks/{notebook.blob_path}")
                try:
                    if not await ctx.backend.exists(key):
                        raise NotebookAssetNotFound(
                            f"Notebook file does not exist at its catalog storage location: {notebook.full_name}"
                        )
                    return await ctx.backend.read_bytes(key)
                finally:
                    await _close_backend(ctx.backend)
            key = storage_settings.notebooks_object_name(notebook.blob_path)
            fs = get_fs()
            if not fs.exists(storage_settings.STORAGE_NOTEBOOKS_BUCKET, key):
                raise NotebookAssetNotFound(
                    f"Notebook file does not exist at its catalog storage location: {notebook.full_name}"
                )
            return fs.read_text(storage_settings.STORAGE_NOTEBOOKS_BUCKET, key).encode("utf-8")
        finally:
            db.close()


notebook_assets: NotebookAssetResolver = CatalogNotebookAssetResolver()


def missing_notebook_targets(
    task_definitions: list[dict],
    workspace_id: str | None = None,
) -> list[str]:
    missing: list[str] = []
    for task in task_definitions or []:
        if task.get("task_type") != "notebook" or not task.get("target_ref"):
            continue
        target = str(task["target_ref"])
        try:
            exists = notebook_assets.exists(target, workspace_id=workspace_id)
        except NotebookAssetNotFound:
            exists = False
        if not exists:
            missing.append(target)
    return missing
