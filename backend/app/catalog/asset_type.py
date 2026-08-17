"""
CatalogAssetType — pluggable protocol for catalog asset kinds (table, volume, notebook, …).

Adding a new asset kind
-----------------------
1. Create a class that implements CatalogAssetType.
2. Call register_asset_type(MyAssetType()) anywhere at import time (e.g. bottom of this file).

The registry is consulted by service.py whenever it needs to resolve the storage
path or perform storage-side cleanup for any asset kind.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.catalog.storage_context import StorageContext


# ---------------------------------------------------------------------------
# Protocol definition
# ---------------------------------------------------------------------------

@runtime_checkable
class CatalogAssetType(Protocol):
    """
    A pluggable descriptor for one kind of catalog asset.

    Implementations decide:
    - How to compute the canonical storage sub-path for an asset.
    - How to clean up storage artefacts when an asset is deleted.
    """

    @property
    def kind(self) -> str:
        """Unique string identifier for this asset type, e.g. 'table', 'volume', 'notebook'."""
        ...

    def storage_sub_path(self, asset_name: str) -> str:
        """
        Return the sub-path (relative to schema_abs_base) for this asset.
        e.g.  'tables/my_table'  or  'volumes/my_volume'
        """
        ...

    async def on_delete(self, ctx: "StorageContext", asset_name: str) -> None:
        """
        Called when the asset is deleted from the catalog.
        Perform any necessary storage cleanup here.
        Default: no-op (override only when storage artefacts exist).
        """
        ...


# ---------------------------------------------------------------------------
# Built-in implementations
# ---------------------------------------------------------------------------

class TableAssetType:
    """Tables store Iceberg metadata + Parquet data under <schema>/tables/<name>."""

    kind = "table"

    def storage_sub_path(self, asset_name: str) -> str:
        return f"tables/{asset_name}"

    async def on_delete(self, ctx: "StorageContext", asset_name: str) -> None:
        # Table deletion currently managed by IcebergManager; no extra cleanup here.
        pass


class VolumeAssetType:
    """Volumes are raw file containers under <schema>/volumes/<name>/."""

    kind = "volume"

    def storage_sub_path(self, asset_name: str) -> str:
        return f"volumes/{asset_name}"

    async def on_delete(self, ctx: "StorageContext", asset_name: str) -> None:
        # Volumes: optionally delete all blobs under the volume prefix.
        sub = self.storage_sub_path(asset_name)
        rel = ctx.rel_path(sub)
        try:
            files = await ctx.backend.list_files(rel + "/")
            for f in files:
                try:
                    await ctx.backend.delete(f.file_path)
                except Exception:
                    pass
        except Exception:
            pass


class NotebookAssetType:
    """Notebooks are .ipynb files under <schema>/notebooks/<blob_path>."""

    kind = "notebook"

    def storage_sub_path(self, asset_name: str) -> str:
        # asset_name for notebooks is the blob_path (uuid.ipynb)
        return f"notebooks/{asset_name}"

    async def on_delete(self, ctx: "StorageContext", asset_name: str) -> None:
        sub = self.storage_sub_path(asset_name)
        rel = ctx.rel_path(sub)
        try:
            if await ctx.backend.exists(rel):
                await ctx.backend.delete(rel)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to delete notebook blob %s", rel)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, CatalogAssetType] = {}


def register_asset_type(impl: CatalogAssetType) -> None:
    """Register an asset type implementation. Replaces any existing entry for the same kind."""
    _REGISTRY[impl.kind] = impl


def get_asset_type(kind: str) -> CatalogAssetType | None:
    """Return the registered implementation for the given kind, or None."""
    return _REGISTRY.get(kind)


def get_asset_type_required(kind: str) -> CatalogAssetType:
    """Return the registered implementation or raise ValueError."""
    impl = _REGISTRY.get(kind)
    if impl is None:
        raise ValueError(
            f"No CatalogAssetType registered for kind '{kind}'. "
            f"Available: {list(_REGISTRY.keys())}"
        )
    return impl


class DashboardAssetType:
    """Dashboards are database-backed assets under <schema>/dashboards/<name>."""

    kind = "dashboard"

    def storage_sub_path(self, asset_name: str) -> str:
        return f"dashboards/{asset_name}"

    async def on_delete(self, ctx: "StorageContext", asset_name: str) -> None:
        pass


# Register built-in types
register_asset_type(TableAssetType())
register_asset_type(VolumeAssetType())
register_asset_type(NotebookAssetType())
register_asset_type(DashboardAssetType())

