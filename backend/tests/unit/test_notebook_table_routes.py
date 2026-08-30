import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app.catalog.schemas import (
    NotebookTableCreateRequest,
    NotebookTableWriteRequest,
    NotebookTableColumnDef,
)
from app.catalog.models import (
    UnifiedCatalog,
    UnifiedCatalogSchema,
    UnifiedCatalogTable,
    UnifiedCatalogColumn,
    CatalogTableType,
)
from app.catalog.routes import create_table_from_notebook, write_table_from_notebook


def _permissive_guard() -> MagicMock:
    """A guard that allows everything.

    These tests exercise table creation and schema validation, not access
    control — that is covered by the governance suite. Calling the handlers
    directly bypasses FastAPI's dependency injection, so the guard has to be
    supplied by hand.
    """
    guard = MagicMock()
    guard.require.return_value = None
    guard.can.return_value = True
    guard.claim_ownership.return_value = None
    return guard


def test_create_table_iceberg_route(monkeypatch):
    async def _test():
        mock_db = MagicMock()
        mock_request = MagicMock()
        user = {"id": "user-123", "email": "test@compassx.com"}

        fake_catalog = UnifiedCatalog(id="cat-1", name="test_cat", catalog_type="iceberg", created_by="user-123")
        fake_schema = UnifiedCatalogSchema(id="sch-1", catalog_id="cat-1", name="test_sch", created_by="user-123")

        mock_db.query().filter().first.side_effect = [
            fake_catalog,  # Catalog query
            fake_schema,   # Schema query
            None,          # Existing table query (None = doesn't exist)
        ]

        mock_storage = MagicMock()
        mock_storage.backend.write_bytes = AsyncMock()
        mock_storage.abs_path = lambda p: f"/abs/{p}"
        mock_storage.rel_path = lambda p: f"rel/{p}"
        mock_storage.backend_base = "s3://bucket/"

        monkeypatch.setattr("app.catalog.service.resolve_catalog_storage", lambda db, cat, sch: mock_storage)
        monkeypatch.setattr(
            "app.catalog.iceberg_manager.IcebergManager.create_table",
            AsyncMock(return_value="rel/tables/my_table/metadata/v1.metadata.json"),
        )
        monkeypatch.setattr("app.catalog.search_indexer.enqueue_asset_for_embedding", MagicMock())

        req = NotebookTableCreateRequest(
            table_ref="test_cat.test_sch.my_table",
            data=[{"turbine_id": "T1", "power_kw": 100.5}],
            mode="overwrite",
            description="Test Iceberg Table",
        )

        result = await create_table_from_notebook(mock_request, req, db=mock_db, user=user, guard=_permissive_guard())
        assert result["status"] == "ok"
        assert result["table_ref"] == "test_cat.test_sch.my_table"
        assert result["engine"] == "iceberg"
        assert result["rows_written"] == 1

    asyncio.run(_test())


def test_write_table_schema_mismatch_route():
    async def _test():
        mock_db = MagicMock()
        mock_request = MagicMock()
        user = {"id": "user-123", "email": "test@compassx.com"}

        fake_catalog = UnifiedCatalog(id="cat-1", name="test_cat", catalog_type="iceberg", created_by="user-123")
        fake_schema = UnifiedCatalogSchema(id="sch-1", catalog_id="cat-1", name="test_sch", created_by="user-123")
        fake_col1 = UnifiedCatalogColumn(name="turbine_id", data_type="string", ordinal=1)
        fake_col2 = UnifiedCatalogColumn(name="power_kw", data_type="float64", ordinal=2)
        fake_table = UnifiedCatalogTable(
            id="tbl-1",
            schema_id="sch-1",
            name="my_table",
            table_type=CatalogTableType.ICEBERG,
            owner="user-123",
            created_by="user-123",
        )
        fake_table.columns = [fake_col1, fake_col2]

        mock_db.query().filter().first.side_effect = [
            fake_catalog,
            fake_schema,
            fake_table,
        ]

        # Incoming data is missing power_kw and has extra extra_col
        req = NotebookTableWriteRequest(
            table_ref="test_cat.test_sch.my_table",
            data=[{"turbine_id": "T2", "extra_col": "extra"}],
            mode="append",
        )

        with pytest.raises(HTTPException) as exc_info:
            await write_table_from_notebook(mock_request, req, db=mock_db, user=user, guard=_permissive_guard())

        assert exc_info.value.status_code == 422
        detail = exc_info.value.detail
        assert detail["error_type"] == "schema_mismatch"
        assert "power_kw" in detail["details"]["missing_columns"]
        assert "extra_col" in detail["details"]["extra_columns"]

    asyncio.run(_test())


def test_write_table_not_found_route():
    async def _test():
        mock_db = MagicMock()
        mock_request = MagicMock()
        user = {"id": "user-123", "email": "test@compassx.com"}

        fake_catalog = UnifiedCatalog(id="cat-1", name="test_cat", catalog_type="iceberg", created_by="user-123")
        fake_schema = UnifiedCatalogSchema(id="sch-1", catalog_id="cat-1", name="test_sch", created_by="user-123")

        mock_db.query().filter().first.side_effect = [
            fake_catalog,
            fake_schema,
            None,  # Table not found
        ]

        req = NotebookTableWriteRequest(
            table_ref="test_cat.test_sch.non_existent",
            data=[{"a": 1}],
            mode="append",
        )

        with pytest.raises(HTTPException) as exc_info:
            await write_table_from_notebook(mock_request, req, db=mock_db, user=user, guard=_permissive_guard())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error_type"] == "table_not_found"

    asyncio.run(_test())
