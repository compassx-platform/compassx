"""Postgres reader port.

The browse and connection functions in ``infrastructure.postgres_reader`` are
the adapter. Callers that are not those functions go through this object.
"""
from __future__ import annotations

from typing import Any, Protocol


class PostgresReader(Protocol):
    def get_connection(self, db, connection_id: Any) -> Any: ...
    def connect_record(self, record: Any, database: str | None = None): ...


class CatalogPostgresReader:
    def get_connection(self, db, connection_id: Any) -> Any:
        from app.catalog.runtime import _get_connection

        return _get_connection(db, connection_id)

    def connect_record(self, record: Any, database: str | None = None):
        from app.catalog.runtime import _connect_record

        return _connect_record(record, database)
