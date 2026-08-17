from types import SimpleNamespace
import pytest

from app.catalog import CatalogTool
from app.agents.services.agent.tools.registry import get_tool_definitions


def test_catalog_tool_definition_registered():
    definitions = get_tool_definitions(["catalog"])

    assert len(definitions) == 1
    function = definitions[0]["function"]
    assert function["name"] == "catalog"
    assert "search_catalog" in function["parameters"]["properties"]["operation"]["enum"]
    assert "get_asset_schema" in function["parameters"]["properties"]["operation"]["enum"]


def test_unknown_operation_returns_tool_error():
    result = CatalogTool().execute(
        {"operation": "non_existent_op", "payload": {}},
        agent=SimpleNamespace(id="tester"),
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
