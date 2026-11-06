"""Wires the catalog ports. Application types are constructed by their module functions."""
from __future__ import annotations

from app.catalog.shared.log import LoggingCatalogLog
from app.catalog.shared.postgres_reader import CatalogPostgresReader
from app.catalog.shared.search_index import SqlSearchIndex

_log = LoggingCatalogLog()
_search = SqlSearchIndex()
_postgres = CatalogPostgresReader()


def catalog_log() -> LoggingCatalogLog:
    return _log


def search_index() -> SqlSearchIndex:
    return _search


def postgres_reader() -> CatalogPostgresReader:
    return _postgres
