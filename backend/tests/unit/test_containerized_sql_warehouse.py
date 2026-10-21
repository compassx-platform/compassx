"""Unit tests for containerized multi-engine SQL Warehouse functionality."""
import asyncio
import pytest
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.sql_warehouse.models import SqlWarehouse
from app.sql_warehouse.routes import run_query, set_default_wh
from app.sql_warehouse.schemas import QueryRequest, WarehouseCreate
from app.sql_warehouse.warehouse.manager import (
    create_warehouse,
    get_default_warehouse,
    get_warehouse_by_id,
    list_warehouses,
    set_default_warehouse,
)
from app.sql_warehouse.warehouse.pod_orchestrator import WarehousePodOrchestrator


def test_default_warehouse_lifecycle(db_session: Session):
    ws_id = "test-ws-abc"

    # 1. First warehouse in workspace should automatically become default
    wh1 = create_warehouse(
        db_session,
        WarehouseCreate(name="duckdb-wh-1", engine="duckdb"),
        created_by="user-1",
        workspace_id=ws_id,
    )
    assert wh1.is_default is True

    # 2. Second warehouse in same workspace should NOT be default
    wh2 = create_warehouse(
        db_session,
        WarehouseCreate(name="clickhouse-wh-2", engine="clickhouse"),
        created_by="user-1",
        workspace_id=ws_id,
    )
    assert wh2.is_default is False

    # 3. get_default_warehouse returns wh1
    default_wh = get_default_warehouse(db_session, workspace_id=ws_id)
    assert default_wh is not None
    assert default_wh.id == wh1.id

    # 4. Set wh2 as default
    set_default_warehouse(db_session, wh2.id, workspace_id=ws_id)
    db_session.refresh(wh1)
    db_session.refresh(wh2)

    assert wh1.is_default is False
    assert wh2.is_default is True

    # 5. get_default_warehouse now returns wh2
    default_wh_after = get_default_warehouse(db_session, workspace_id=ws_id)
    assert default_wh_after.id == wh2.id


def test_warehouse_pod_orchestrator_specs():
    orchestrator = WarehousePodOrchestrator()

    # DuckDB warehouse
    duck_wh = SqlWarehouse(
        id="wh-duckdb-12345",
        workspace_id="ws-1",
        name="Main DuckDB",
        engine="duckdb",
        resource_policy={"max_memory_mb": 4096, "max_threads": 4},
    )
    duck_spec = orchestrator._build_spec(duck_wh)
    assert "compute-duckdb" in duck_spec.container_image
    assert any(p.container_port == 8080 for p in duck_spec.ports)
    assert duck_spec.resources.memory_limit == "4096Mi"
    assert duck_spec.resources.cpu_limit == "4"

    # ClickHouse warehouse
    ch_wh = SqlWarehouse(
        id="wh-clickhouse-67890",
        workspace_id="ws-1",
        name="ClickHouse Analytics",
        engine="clickhouse",
        resource_policy={},
    )
    ch_spec = orchestrator._build_spec(ch_wh)
    assert "clickhouse" in ch_spec.container_image
    assert any(p.container_port == 8123 for p in ch_spec.ports)
    assert any(p.container_port == 9000 for p in ch_spec.ports)


@pytest.mark.asyncio
async def test_run_query_auto_resolves_default_warehouse(db_session: Session):
    ws_id = "test-ws-query-default"

    # Create default warehouse
    wh = create_warehouse(
        db_session,
        WarehouseCreate(name="default-duckdb", engine="duckdb"),
        created_by="user-1",
        workspace_id=ws_id,
    )
    wh.status = "running"
    db_session.commit()

    # Mock request with workspace context
    class DummyState:
        workspace = None
    class DummyRequest:
        state = DummyState()
        headers = {"X-Workspace-Id": ws_id}
        query_params = {}

    req = QueryRequest(warehouse_id=None, sql="SELECT 42 AS answer")
    user = {"id": "user-1", "name": "Test User"}

    res = await run_query(
        request=DummyRequest(),
        req=req,
        db=db_session,
        data_db=db_session,
        user=user,
    )

    assert "rows" in res
    assert res["rows"] == [[42]]
    assert res["warehouse_id"] == wh.id or "query_id" in res
