"""StorageService — CRUD for storage backends using SQLAlchemy Session."""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from .db_models import StorageBackend
from .factory import build_backend
from .backend import BlobStorageBackend
from .models import StorageBackendCreate, StorageBackendRead, StorageProvider
from app.services.encryption import encrypt_field

logger = logging.getLogger(__name__)


class StorageService:
    """
    Manages storage backend registrations in Postgres.
    Provides an in-process cache of constructed backend instances.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BlobStorageBackend] = {}

    def register_backend(self, db: Session, data: StorageBackendCreate, registered_by: str) -> StorageBackendRead:
        if data.is_default:
            db.query(StorageBackend).update({"is_default": False})

        existing = db.query(StorageBackend).filter(StorageBackend.name == data.name).first()

        if data.provider == StorageProvider.AZURE:
            c = data.azure
            if not c:
                raise ValueError("Azure credentials required for azure provider")
            kwargs = dict(
                name=data.name,
                provider=data.provider.value,
                is_default=data.is_default,
                azure_account_name=c.account_name,
                azure_container=c.container,
                azure_base_path=c.base_path,
                encrypted_azure_account_key=encrypt_field(c.account_key) if c.account_key else None,
                azure_tenant_id=c.tenant_id,
                azure_client_id=c.client_id,
                encrypted_azure_client_secret=encrypt_field(c.client_secret) if c.client_secret else None,
                created_by=registered_by,
            )
        else:
            c = data.s3
            if not c:
                raise ValueError("S3 credentials required for s3/minio provider")
            kwargs = dict(
                name=data.name,
                provider=data.provider.value,
                is_default=data.is_default,
                s3_bucket=c.bucket,
                s3_base_path=c.base_path,
                s3_region=c.region,
                s3_endpoint_url=c.endpoint_url,
                encrypted_access_key=encrypt_field(c.access_key),
                encrypted_secret_key=encrypt_field(c.secret_key),
                created_by=registered_by,
            )

        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            backend = existing
        else:
            backend = StorageBackend(**kwargs)
            db.add(backend)

        db.commit()
        db.refresh(backend)
        self._cache.pop(data.name, None)
        return self._to_read(backend)

    def get_backend(self, db: Session, name: str) -> BlobStorageBackend:
        if name in self._cache:
            return self._cache[name]
        row = db.query(StorageBackend).filter(StorageBackend.name == name).first()
        if not row:
            raise ValueError(f"Storage backend '{name}' not found")
        instance = build_backend(self._row_to_dict(row))
        self._cache[name] = instance
        return instance

    def get_default_backend(self, db: Session) -> tuple[str, BlobStorageBackend]:
        row = db.query(StorageBackend).filter(StorageBackend.is_default.is_(True)).first()
        if not row:
            raise ValueError("No default storage backend configured")
        return row.name, build_backend(self._row_to_dict(row))

    def list_backends(self, db: Session) -> list[StorageBackendRead]:
        rows = db.query(StorageBackend).order_by(StorageBackend.created_at).all()
        return [self._to_read(r) for r in rows]

    def delete_backend(self, db: Session, name: str) -> None:
        row = db.query(StorageBackend).filter(StorageBackend.name == name).first()
        if not row:
            raise ValueError(f"Storage backend '{name}' not found")
        db.delete(row)
        db.commit()
        self._cache.pop(name, None)

    async def test_connection(self, db: Session, name: str) -> dict:
        try:
            backend = self.get_backend(db, name)
            files = await backend.list_files("")
            return {"status": "ok", "reachable": True, "file_count": len(files)}
        except Exception as e:
            logger.warning("Storage backend test failed for %s: %s", name, e)
            return {"status": "error", "reachable": False, "error": str(e)}

    def _row_to_dict(self, row: StorageBackend) -> dict:
        return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    def _to_read(self, row: StorageBackend) -> StorageBackendRead:
        if row.provider == "azure":
            container_or_bucket = row.azure_container or ""
            base_path = row.azure_base_path or "compassx/"
        else:
            container_or_bucket = row.s3_bucket or ""
            base_path = row.s3_base_path or "compassx/"
        return StorageBackendRead(
            id=row.id,
            name=row.name,
            provider=StorageProvider(row.provider),
            is_default=row.is_default,
            container_or_bucket=container_or_bucket,
            base_path=base_path,
            created_at=row.created_at,
        )


# Singleton — shared across request handlers
storage_service = StorageService()
