"""
StorageContext — resolved storage configuration for a catalog/schema.

All path computation lives here so service.py stays free of
provider-specific branching (no more `if azure / else s3`).

Usage
-----
    ctx = resolve_catalog_storage(db, catalog_name, schema_name)
    if not ctx:
        raise ValueError("No storage backend configured")

    abs_path = ctx.abs_path("tables/my_table")   # absolute from container root
    rel_path = ctx.rel_path("tables/my_table")   # relative — pass to backend calls
    backend  = ctx.backend                       # BlobStorageBackend instance
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.storage.backend import BlobStorageBackend


@dataclass
class StorageContext:
    """Fully-resolved storage location context for a catalog (or schema)."""

    backend: "BlobStorageBackend"
    backend_base: str           # prefix the backend prepends internally  e.g. "compassx/"
    schema_abs_base: str        # absolute path from container root for this schema namespace
    #                             e.g. "compassx/my_catalog/my_schema"

    # ------------------------------------------------------------------ helpers

    def abs_path(self, relative: str) -> str:
        """Build an absolute path (container-root-relative) for a given sub-path."""
        return f"{self.schema_abs_base.rstrip('/')}/{relative.lstrip('/')}"

    def rel_path(self, relative: str) -> str:
        """
        Build a backend-relative path (i.e. remove backend_base prefix).
        Pass this to backend.write_bytes / read_bytes / etc.
        """
        abs_ = self.abs_path(relative)
        base = self.backend_base.rstrip("/")
        if abs_.startswith(base + "/"):
            return abs_[len(base) + 1:]
        return abs_


def _get_backend_base(backend_row) -> str:
    """Extract the base_path from a StorageBackend ORM row, normalised to end with '/'."""
    if backend_row.provider == "azure":
        raw = backend_row.azure_base_path or "compassx/"
    else:
        raw = backend_row.s3_base_path or "compassx/"
    return raw.rstrip("/") + "/"


def resolve_catalog_storage(
    db: "Session",
    catalog_name: str,
    schema_name: str,
    workspace_id: str | None = None,
) -> "StorageContext | None":
    """
    Resolve storage for a schema by walking up:
      1. Schema-level storage_backend_id (legacy / explicit override)
      2. Catalog-level storage_backend_id  (new default)
      3. Storage of the workspace bound to the catalog

    Returns None when neither level has storage configured.

    The schema_abs_base follows the convention:
        <backend_base><catalog_name>/<schema_name>
    overridden by schema.base_path if explicitly set (backward compat).
    """
    from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema
    from app.storage.db_models import StorageBackend
    from app.storage.service import storage_service

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not catalog:
        return None

    schema = (
        db.query(UnifiedCatalogSchema)
        .filter(
            UnifiedCatalogSchema.catalog_id == catalog.id,
            UnifiedCatalogSchema.name == schema_name,
        )
        .first()
    )

    # Determine which storage_backend_id to use: schema first, then catalog
    backend_id: str | None = None
    explicit_base_path: str | None = None

    if schema and schema.storage_backend_id:
        backend_id = schema.storage_backend_id
        explicit_base_path = schema.base_path  # may be None
    elif catalog.storage_backend_id:  # type: ignore[attr-defined]
        backend_id = catalog.storage_backend_id  # type: ignore[attr-defined]
        explicit_base_path = None  # compute from catalog/schema names

    backend_row = None
    if backend_id:
        backend_row = db.query(StorageBackend).filter(StorageBackend.id == backend_id).first()

    if not backend_row:
        # Fall back to workspace-level storage
        from app.workspace.models import Workspace
        from app.workspace.storage_validator import decrypt_storage_config
        from app.storage.azure_backend import AzureStorageBackend
        from app.storage.s3_backend import S3StorageBackend
        from app.storage.minio_backend import MinIOStorageBackend

        from app.catalog.models import CatalogWorkspaceBinding

        bindings = db.query(CatalogWorkspaceBinding).filter(
            CatalogWorkspaceBinding.catalog_id == catalog.id,
        )
        if workspace_id:
            binding = bindings.filter(
                CatalogWorkspaceBinding.workspace_id == workspace_id,
            ).first()
        else:
            candidates = bindings.all()
            binding = candidates[0] if len(candidates) == 1 else None

        # Storage inheritance must be deterministic. Selecting an arbitrary
        # active workspace can read another tenant's container.
        workspace = (
            db.query(Workspace).filter(
                Workspace.id == str(binding.workspace_id),
                Workspace.status == "active",
            ).first()
            if binding
            else None
        )
        if not workspace or not workspace.storage_backend:
            return None

        provider = workspace.storage_backend
        config = decrypt_storage_config(workspace.storage_config)

        if provider == "azure":
            backend_instance = AzureStorageBackend(
                account_name=config.get("account_name"),
                container=config.get("container"),
                base_path=config.get("prefix") or "compassx/",
                account_key=config.get("account_key"),
            )
            backend_base = (config.get("prefix") or "compassx/").rstrip("/") + "/"
        elif provider == "s3":
            backend_instance = S3StorageBackend(
                bucket=config.get("bucket"),
                base_path=config.get("prefix") or "compassx/",
                region=config.get("region") or "us-east-1",
                access_key=config.get("access_key"),
                secret_key=config.get("secret_key"),
            )
            backend_base = (config.get("prefix") or "compassx/").rstrip("/") + "/"
        elif provider == "minio":
            backend_instance = MinIOStorageBackend(
                bucket=config.get("bucket"),
                base_path=config.get("prefix") or "compassx/",
                endpoint_url=config.get("endpoint"),
                access_key=config.get("access_key"),
                secret_key=config.get("secret_key"),
            )
            backend_base = (config.get("prefix") or "compassx/").rstrip("/") + "/"
        else:
            return None

        schema_abs_base = f"{backend_base}{catalog_name}/{schema_name}"

        return StorageContext(
            backend=backend_instance,
            backend_base=backend_base,
            schema_abs_base=schema_abs_base,
        )

    backend_base = _get_backend_base(backend_row)
    backend_instance = storage_service.get_backend(db, backend_row.name)

    if explicit_base_path:
        schema_abs_base = explicit_base_path.rstrip("/")
    else:
        schema_abs_base = f"{backend_base}{catalog_name}/{schema_name}"

    return StorageContext(
        backend=backend_instance,
        backend_base=backend_base,
        schema_abs_base=schema_abs_base,
    )


def resolve_catalog_storage_by_schema_id(
    db: "Session",
    schema_id: str,
    workspace_id: str | None = None,
) -> "StorageContext | None":
    """
    Convenience: resolve storage given only the schema PK.
    Falls back to catalog-level storage if schema has none.
    """
    from app.catalog.models import UnifiedCatalogSchema, UnifiedCatalog

    schema = db.query(UnifiedCatalogSchema).filter(UnifiedCatalogSchema.id == schema_id).first()
    if not schema:
        return None

    catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.id == schema.catalog_id).first()
    if not catalog:
        return None

    return resolve_catalog_storage(
        db,
        catalog.name,
        schema.name,
        workspace_id=workspace_id,
    )
