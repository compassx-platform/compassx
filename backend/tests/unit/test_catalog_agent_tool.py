from types import SimpleNamespace
import pytest

from app.catalog import CatalogTool
from app.agents.services.agent.tools.registry import get_tool_definitions


def test_catalog_tool_definition_registered():
    definitions = get_tool_definitions(["catalog"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "catalog"
    assert "list_tables" in function["parameters"]["properties"]["operation"]["enum"]
    assert "search_catalog" in function["parameters"]["properties"]["operation"]["enum"]
    assert "get_asset_schema" in function["parameters"]["properties"]["operation"]["enum"]
    assert "search_catalog_metadata" in function["parameters"]["properties"]["operation"]["enum"]


def test_unknown_operation_returns_tool_error():
    result = CatalogTool().execute(
        {"operation": "non_existent_op", "payload": {}},
        agent=SimpleNamespace(id="tester", workspace_id=None),
        db=SimpleNamespace(),
    )

    assert result.ok is False
    assert "Unsupported catalog operation" in result.error
    assert result.result["tool"] == "non_existent_op"


def test_payload_must_be_object():
    result = CatalogTool().execute(
        {"operation": "search_catalog", "payload": "not-an-object"},
        agent=SimpleNamespace(id="tester", workspace_id=None),
        db=SimpleNamespace(),
    )

    assert result.ok is False
    assert result.error == "payload must be an object"


def test_catalog_tool_workspace_scoping_denied():
    from unittest.mock import patch
    with patch("app.catalog.tools._is_catalog_allowed", return_value=False):
        result = CatalogTool().execute(
            {"operation": "get_asset_schema", "payload": {"full_name": "restricted_catalog.schema.table"}},
            agent=SimpleNamespace(id="tester", workspace_id="test-workspace"),
            db=SimpleNamespace(),
        )
        assert result.ok is False
        assert "Access denied" in result.error


def test_catalog_tool_workspace_scoping_allowed():
    from unittest.mock import patch
    with patch("app.catalog.tools._is_catalog_allowed", return_value=True), \
         patch("app.catalog.service.get_table") as mock_get_table:
        mock_get_table.return_value = SimpleNamespace(
            description="Allowed table",
            columns=[
                SimpleNamespace(name="id", data_type="integer", description="", nullable=False, ordinal=1)
            ],
            properties={"row_estimate": 100}
        )
        result = CatalogTool().execute(
            {"operation": "get_asset_schema", "payload": {"full_name": "allowed_catalog.schema.table"}},
            agent=SimpleNamespace(id="tester", workspace_id="test-workspace"),
            db=SimpleNamespace(),
        )
        assert result.ok is True
        assert result.result["full_name"] == "allowed_catalog.schema.table"


def test_catalog_tool_list_tables_denied():
    from unittest.mock import patch
    with patch("app.catalog.tools._is_catalog_allowed", return_value=False):
        result = CatalogTool().execute(
            {"operation": "list_tables", "payload": {"catalog_name": "restricted_catalog"}},
            agent=SimpleNamespace(id="tester", workspace_id="test-workspace"),
            db=SimpleNamespace(),
        )
        assert result.ok is False
        assert "Access denied to catalog 'restricted_catalog'" in result.error


def test_catalog_tool_list_tables_allowed():
    from unittest.mock import patch, MagicMock
    with patch("app.catalog.tools._is_catalog_allowed", return_value=True), \
         patch("app.catalog.tools._get_allowed_catalogs", return_value=["test_catalog"]):
        mock_account_db = MagicMock()
        mock_table = SimpleNamespace(
            id="t1",
            name="orders",
            table_type="iceberg",
            description="Orders table",
            owner="admin",
            columns=[SimpleNamespace(name="order_id"), SimpleNamespace(name="amount")],
            created_at=None,
            schema=SimpleNamespace(
                name="public",
                catalog=SimpleNamespace(name="test_catalog")
            )
        )
        query_mock = MagicMock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [mock_table]
        mock_account_db.query.return_value = query_mock

        with patch("app.database.AccountSessionLocal", return_value=mock_account_db):
            result = CatalogTool().execute(
                {"operation": "list_tables", "payload": {"catalog_name": "test_catalog", "schema_name": "public"}},
                agent=SimpleNamespace(id="tester", workspace_id="test-workspace"),
                db=SimpleNamespace(),
            )
            assert result.ok is True
            assert result.result["count"] == 1
            assert result.result["tables"][0]["full_name"] == "test_catalog.public.orders"
            assert result.result["tables"][0]["columns"] == ["order_id", "amount"]


def test_catalog_tool_search_catalog_empty_query():
    from unittest.mock import patch, MagicMock
    with patch("app.catalog.tools._get_allowed_catalogs", return_value=["test_catalog"]):
        mock_conn = MagicMock()
        mock_row = SimpleNamespace(
            full_name="test_catalog.public.orders",
            object_type="table",
            description="Orders table",
            is_foreign=False,
        )
        mock_conn.execute.return_value.fetchall.return_value = [mock_row]

        with patch("app.database.account_engine.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            result = CatalogTool().execute(
                {"operation": "search_catalog", "payload": {"query": "", "object_type": "table"}},
                agent=SimpleNamespace(id="tester", workspace_id="test-workspace"),
                db=SimpleNamespace(),
            )
            assert result.ok is True
            assert result.result["count"] == 1
            assert result.result["results"][0]["full_name"] == "test_catalog.public.orders"

