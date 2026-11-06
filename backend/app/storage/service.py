"""StorageService — CRUD for storage backends using SQLAlchemy Session."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .backend import BlobStorageBackend
from .models import StorageBackendCreate, StorageBackendRead
from app.storage.registration.application.delete_backend import delete_backend as delete_backend_action
from app.storage.registration.application.get_backend import get_backend as get_backend_action
from app.storage.registration.application.get_default_backend import get_default_backend as get_default_backend_action
from app.storage.registration.application.list_backends import list_backends as list_backends_action
from app.storage.registration.application.register_backend import register_backend as register_backend_action
from app.storage.registration.application.test_connection import test_connection as test_connection_action
from app.storage.shared.support import _row_to_dict, _to_read

__all__ = ["StorageService", "storage_service", "_row_to_dict", "_to_read"]


class StorageService:
    """
    Manages storage backend registrations in Postgres.
    Provides an in-process cache of constructed backend instances.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BlobStorageBackend] = {}

    def register_backend(self, db: Session, data: StorageBackendCreate, registered_by: str) -> StorageBackendRead:
        return register_backend_action(db, data, registered_by, self._cache)

    def get_backend(self, db: Session, name: str) -> BlobStorageBackend:
        return get_backend_action(db, name, self._cache)

    def get_default_backend(self, db: Session) -> tuple[str, BlobStorageBackend]:
        return get_default_backend_action(db)

    def list_backends(self, db: Session) -> list[StorageBackendRead]:
        return list_backends_action(db)

    def delete_backend(self, db: Session, name: str) -> None:
        return delete_backend_action(db, name, self._cache)

    async def test_connection(self, db: Session, name: str) -> dict:
        return await test_connection_action(db, name, self._cache)


# Singleton — shared across request handlers
storage_service = StorageService()
