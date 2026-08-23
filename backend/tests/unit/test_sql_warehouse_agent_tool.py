from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.agents.services.agent.tools.platform.sql_warehouse.sql_warehouse_tool import SqlWarehouseTool
from app.agents.services.agent.tools.platform.sql_warehouse.operations import (
    execute_sql_warehouse_operation,
    SQL_WAREHOUSE_OPERATIONS,
)
from app.agents.services.agent.tools.registry import get_tool_definitions, tool_registry


def test_sql_warehouse_tool_registered_in_registry():
    tool = tool_registry.get("sql_warehouse")
    assert tool is not None
    assert tool.key == "sql_warehouse"
    assert tool.name == "SQL Warehouse"

    defs = get_tool_definitions(["sql_warehouse"])
    assert len(defs) == 1
    fn = defs[0]["function"]
    assert fn["name"] == "sql_warehouse"
    assert "properties" in fn["parameters"]
    assert "operation" in fn["parameters"]["properties"]
    assert "sql" in fn["parameters"]["properties"]


def test_sql_warehouse_unsupported_operation():
    tool = SqlWarehouseTool()
    agent = SimpleNamespace(id=1, name="TestAgent", created_by="test_user", workspace_id="ws-1")
    db = MagicMock()

    result = tool.execute(
        {"operation": "invalid_op", "payload": {}},
        agent=agent,
        db=db,
    )
    assert result.ok is False
    assert "Unsupported sql_warehouse operation" in result.error


def test_sql_warehouse_missing_sql():
    tool = SqlWarehouseTool()
    agent = SimpleNamespace(id=1, name="TestAgent", created_by="test_user", workspace_id="ws-1")
    db = MagicMock()

    result = tool.execute(
        {"operation": "execute_query", "payload": {}},
        agent=agent,
        db=db,
    )
    assert result.ok is False
    assert "Missing required parameter 'sql'" in result.error


def test_sql_warehouse_flat_sql_invocation(monkeypatch):
    tool = SqlWarehouseTool()
    agent = SimpleNamespace(id=1, name="TestAgent", created_by="test_user", workspace_id="ws-1")
    db = MagicMock()

    fake_wh = SimpleNamespace(
        id="wh-1",
        name="test_duckdb",
        engine="duckdb",
        status="running",
        resource_policy={},
    )

    fake_query_result = {
        "query_id": "qid-123",
        "columns": ["id", "val"],
        "rows": [{"id": 1, "val": "hello"}],
        "rows_returned": 1,
        "truncated": False,
        "duration_ms": 12,
        "cache_hit": False,
        "query_analysis": None,
    }

    monkeypatch.setattr(
        "app.agents.services.agent.tools.platform.sql_warehouse.operations.list_warehouses",
        lambda db, workspace_id=None: [fake_wh],
    )

    mock_run = AsyncMock(return_value=fake_query_result)
    monkeypatch.setattr(
        "app.agents.services.agent.tools.platform.sql_warehouse.operations.QueryExecutor.run",
        mock_run,
    )

    result = tool.execute(
        {"sql": "SELECT 1 as id, 'hello' as val"},
        agent=agent,
        db=db,
    )

    assert result.ok is True
    data = result.result
    assert data["query_id"] == "qid-123"
    assert data["rowCount"] == 1
    assert data["columns"] == ["id", "val"]
    assert data["warehouse_id"] == "wh-1"
    assert data["warehouse_name"] == "test_duckdb"


def test_sql_warehouse_stopped_warehouse_error(monkeypatch):
    tool = SqlWarehouseTool()
    agent = SimpleNamespace(id=1, name="TestAgent", created_by="test_user", workspace_id="ws-1")
    db = MagicMock()

    fake_wh = SimpleNamespace(
        id="wh-stopped",
        name="stopped_wh",
        engine="duckdb",
        status="stopped",
        resource_policy={},
    )

    monkeypatch.setattr(
        "app.agents.services.agent.tools.platform.sql_warehouse.operations.list_warehouses",
        lambda db, workspace_id=None: [fake_wh],
    )

    result = tool.execute(
        {"operation": "execute_query", "payload": {"sql": "SELECT 1"}},
        agent=agent,
        db=db,
    )

    assert result.ok is False
    assert "currently stopped" in result.error


def test_sql_warehouse_list_warehouses_operation(monkeypatch):
    tool = SqlWarehouseTool()
    agent = SimpleNamespace(id=1, name="TestAgent", created_by="test_user", workspace_id="ws-1")
    db = MagicMock()

    fake_wh1 = SimpleNamespace(
        id="wh-1",
        name="Main DuckDB",
        description="Default warehouse",
        engine="duckdb",
        status="running",
        resource_policy={},
        created_at=None,
    )
    fake_wh2 = SimpleNamespace(
        id="wh-2",
        name="ClickHouse Analytics",
        description="OLAP warehouse",
        engine="clickhouse",
        status="stopped",
        resource_policy={},
        created_at=None,
    )

    monkeypatch.setattr(
        "app.agents.services.agent.tools.platform.sql_warehouse.operations.list_warehouses",
        lambda db, workspace_id=None: [fake_wh1, fake_wh2],
    )

    result = tool.execute(
        {"operation": "list_warehouses", "payload": {}},
        agent=agent,
        db=db,
    )

    assert result.ok is True
    data = result.result
    assert data["count"] == 2
    assert data["warehouses"][0]["name"] == "Main DuckDB"
    assert data["warehouses"][0]["status"] == "running"
    assert data["warehouses"][1]["name"] == "ClickHouse Analytics"


def test_sql_warehouse_explain_query_operation(monkeypatch):
    tool = SqlWarehouseTool()
    agent = SimpleNamespace(id=1, name="TestAgent", created_by="test_user", workspace_id="ws-1")
    db = MagicMock()

    fake_wh = SimpleNamespace(
        id="wh-1",
        name="test_duckdb",
        engine="duckdb",
        status="running",
        resource_policy={},
    )

    monkeypatch.setattr(
        "app.agents.services.agent.tools.platform.sql_warehouse.operations.list_warehouses",
        lambda db, workspace_id=None: [fake_wh],
    )

    mock_adapter = MagicMock()
    mock_adapter.explain = AsyncMock(return_value="EXPLAIN PLAN:\nSEQ_SCAN [my_table]")
    monkeypatch.setattr(
        "app.agents.services.agent.tools.platform.sql_warehouse.operations.get_adapter",
        lambda wh: mock_adapter,
    )

    result = tool.execute(
        {"operation": "explain_query", "payload": {"sql": "SELECT * FROM my_table"}},
        agent=agent,
        db=db,
    )

    assert result.ok is True
    data = result.result
    assert "EXPLAIN PLAN" in data["plan"]
    assert data["warehouse_id"] == "wh-1"
