"""Search index port. The catalog service enqueues and deletes through this."""
from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session


class SearchIndex(Protocol):
    def enqueue(self, db: Session, **kwargs): ...
    def delete(self, db: Session, object_type: str, source_object_id: str) -> None: ...


class SqlSearchIndex:
    """Looks up the indexer on each call so tests can patch ``app.catalog.search_indexer``."""

    def enqueue(self, db: Session, **kwargs):
        from app.catalog import search_indexer

        return search_indexer.enqueue_asset_for_embedding(db, **kwargs)

    def delete(self, db: Session, object_type: str, source_object_id: str) -> None:
        from app.catalog import search_indexer

        search_indexer.delete_asset_from_search(db, object_type, source_object_id)
