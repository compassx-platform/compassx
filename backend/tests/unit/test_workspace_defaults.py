import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from fastapi import Request
from sqlalchemy.orm import Session

from app.workspace.models import Workspace, Account, Principal
from app.models.compute_resources import ComputeResource
from app.sql_warehouse.models import SqlWarehouse
from app.compute.services.workspace_defaults import ensure_workspace_default_resources
from app.compute.routes.router import list_compute_resources
from app.sql_warehouse.routes import list_wh
from app.compute.schemas import ComputeResourceRequest, RuntimeType, ComputeProfileId
from app.sql_warehouse.schemas import WarehouseCreate
from app.workspace.schemas import WorkspaceCreate
from app.workspace.account_routes import create_workspace


def _mock_request(workspace_id: str | None = None) -> Request:
    request = MagicMock(spec=Request)
    class MockWorkspaceContext:
        def __init__(self, ws_id):
            self.workspace_id = ws_id
    if workspace_id:
        request.state.workspace = MockWorkspaceContext(workspace_id)
    else:
        request.state.workspace = None
    request.app.state.runtime_manager = None
    return request


def _permissive_guard(principal_id: str) -> MagicMock:
    """A guard that allows everything, acting as ``principal_id``.

    This test is about workspace default provisioning, not access control —
    that is covered by the governance suite. Calling the handler directly
    bypasses FastAPI's dependency injection, so the guard has to be supplied
    by hand.
    """
    guard = MagicMock()
    guard.principal.id = principal_id
    guard.require.return_value = None
    guard.can.return_value = True
    return guard


def test_ensure_workspace_default_resources_creates_both(db_session: Session):
    """Test that when a workspace has no compute or warehouse, both are created and running."""
    ws_id = str(uuid4())

    # Verify initially empty
    computes_before = db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws_id).all()
    warehouses_before = db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws_id).all()
    assert len(computes_before) == 0
    assert len(warehouses_before) == 0

    # Ensure defaults
    result = ensure_workspace_default_resources(
        system_db=db_session,
        workspace_id=ws_id,
        created_by="user-admin",
        user_id="user-admin",
    )

    assert result["compute_created"] is True
    assert result["warehouse_created"] is True

    # Verify compute
    computes_after = db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws_id).all()
    assert len(computes_after) == 1
    c = computes_after[0]
    assert c.name == "default"
    assert c.runtime == "duckdb"
    assert c.is_default is True
    assert c.desired_status == "running"
    assert c.workspace_id == ws_id

    # Verify warehouse
    warehouses_after = db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws_id).all()
    assert len(warehouses_after) == 1
    w = warehouses_after[0]
    assert w.name == "default"
    assert w.engine == "duckdb"
    assert w.status == "running"
    assert w.workspace_id == ws_id


def test_ensure_workspace_default_resources_skips_when_both_exist(db_session: Session):
    """Test that if compute and warehouse already exist, none are created."""
    ws_id = str(uuid4())

    # Create initial defaults
    ensure_workspace_default_resources(
        system_db=db_session,
        workspace_id=ws_id,
        created_by="user-admin",
        user_id="user-admin",
    )

    # Call again
    result = ensure_workspace_default_resources(
        system_db=db_session,
        workspace_id=ws_id,
        created_by="user-admin",
        user_id="user-admin",
    )

    assert result["compute_created"] is False
    assert result["warehouse_created"] is False

    # Counts should remain 1
    assert db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws_id).count() == 1
    assert db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws_id).count() == 1


def test_ensure_workspace_default_resources_skips_compute_if_custom_compute_exists(db_session: Session):
    """Test that if a custom compute exists, default compute is not created, but warehouse is created."""
    ws_id = str(uuid4())

    # Create a custom compute resource first
    custom_compute = ComputeResource(
        id=str(uuid4())[:8],
        workspace_id=ws_id,
        name="custom-spark",
        runtime="spark",
        profile="local",
        user_id="user-1",
        created_by="user-1",
        desired_status="stopped",
        is_default=False,
    )
    db_session.add(custom_compute)
    db_session.commit()

    # Ensure defaults
    result = ensure_workspace_default_resources(
        system_db=db_session,
        workspace_id=ws_id,
        created_by="user-1",
        user_id="user-1",
    )

    # Compute was not created (existing compute preserved); warehouse was created
    assert result["compute_created"] is False
    assert result["warehouse_created"] is True

    computes = db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws_id).all()
    assert len(computes) == 1
    assert computes[0].name == "custom-spark"

    warehouses = db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws_id).all()
    assert len(warehouses) == 1
    assert warehouses[0].name == "default"
    assert warehouses[0].engine == "duckdb"
    assert warehouses[0].status == "running"


def test_ensure_workspace_default_resources_skips_warehouse_if_custom_warehouse_exists(db_session: Session):
    """Test that if a custom warehouse exists, default warehouse is not created, but compute is created."""
    ws_id = str(uuid4())

    # Create a custom warehouse first
    custom_wh = SqlWarehouse(
        workspace_id=ws_id,
        name="custom-clickhouse",
        description="ClickHouse cluster",
        engine="clickhouse",
        status="stopped",
        config={},
        resource_policy={},
        created_by="user-1",
    )
    db_session.add(custom_wh)
    db_session.commit()

    # Ensure defaults
    result = ensure_workspace_default_resources(
        system_db=db_session,
        workspace_id=ws_id,
        created_by="user-1",
        user_id="user-1",
    )

    # Warehouse was not created; compute was created
    assert result["compute_created"] is True
    assert result["warehouse_created"] is False

    warehouses = db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws_id).all()
    assert len(warehouses) == 1
    assert warehouses[0].name == "custom-clickhouse"

    computes = db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws_id).all()
    assert len(computes) == 1
    assert computes[0].name == "default"
    assert computes[0].runtime == "duckdb"
    assert computes[0].desired_status == "running"


def test_workspace_defaults_isolation_and_querying(db_session: Session):
    """Test that default resources in WS1 are isolated from WS2."""
    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    ensure_workspace_default_resources(db_session, workspace_id=ws1_id, user_id="user-1")
    ensure_workspace_default_resources(db_session, workspace_id=ws2_id, user_id="user-2")

    req1 = _mock_request(ws1_id)
    req2 = _mock_request(ws2_id)

    # Query compute under ws1 context. The handler resolves the caller from
    # the guard now, so one has to be supplied by hand.
    ws1_computes = list_compute_resources(
        req1, db=db_session, guard=_permissive_guard("user-1")
    )
    assert len(ws1_computes) == 1
    assert ws1_computes[0].name == "default"
    assert ws1_computes[0].runtime == "duckdb"

    # Query compute under ws2 context
    ws2_computes = list_compute_resources(
        req2, db=db_session, guard=_permissive_guard("user-2")
    )
    assert len(ws2_computes) == 1
    assert ws2_computes[0].name == "default"
    assert ws2_computes[0].runtime == "duckdb"

    class MockUser:
        id = "user-1"

    # Query warehouse under ws1 context
    ws1_whs = list_wh(req1, db=db_session, user=MockUser())
    assert len(ws1_whs) == 1
    assert ws1_whs[0].name == "default"
    assert ws1_whs[0].engine == "duckdb"
    assert ws1_whs[0].status == "running"

    # Query warehouse under ws2 context
    ws2_whs = list_wh(req2, db=db_session, user=MockUser())
    assert len(ws2_whs) == 1
    assert ws2_whs[0].name == "default"
    assert ws2_whs[0].engine == "duckdb"
    assert ws2_whs[0].status == "running"


def test_create_workspace_auto_provisions_defaults(db_session: Session):
    """Test that create_workspace endpoint auto-provisions default compute and warehouse."""
    import asyncio
    account = Account(id=str(uuid4()), name="Account 1", slug="account-1")
    db_session.add(account)
    db_session.flush()

    admin = Principal(
        id=str(uuid4()),
        account_id=account.id,
        type="user",
        name="Admin",
        email="admin@test.com",
        is_account_admin=True,
    )
    db_session.add(admin)
    db_session.commit()

    req = _mock_request()
    body = WorkspaceCreate(
        name="Sales Analytics",
        slug="sales-analytics",
        storage_backend="managed",
    )

    # Mock SystemSessionLocal to return a new session on the test DB
    import app.database
    from sqlalchemy.orm import sessionmaker
    orig_sys_session = app.database.SystemSessionLocal
    app.database.SystemSessionLocal = sessionmaker(bind=db_session.bind)
    try:
        ws_out = asyncio.run(create_workspace(body, db=db_session, admin=admin, request=req))
        assert ws_out.slug == "sales-analytics"

        # Check default compute created
        computes = db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws_out.id).all()
        assert len(computes) == 1
        assert computes[0].name == "default"
        assert computes[0].runtime == "duckdb"
        assert computes[0].is_default is True
        assert computes[0].desired_status == "running"

        # Check default warehouse created
        warehouses = db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws_out.id).all()
        assert len(warehouses) == 1
        assert warehouses[0].name == "default"
        assert warehouses[0].engine == "duckdb"
        assert warehouses[0].status == "running"
    finally:
        app.database.SystemSessionLocal = orig_sys_session


def test_setup_complete_auto_provisions_defaults(db_session: Session):
    """Test that setup_complete endpoint auto-provisions default compute and warehouse for initial workspace."""
    from app.user_manager.routes.setup_routes import setup_complete, SetupCompleteIn
    from app.workspace.models import Workspace as LegacyWorkspace

    req = _mock_request()
    body = SetupCompleteIn(
        account_name="Acme Corp",
        admin_email="admin@acme.com",
        admin_password="StrongPassword123!",
        admin_display_name="Admin User",
        workspace_name="Engineering",
    )

    res = setup_complete(body, account_db=db_session, system_db=db_session, request=req)
    assert res.user_id is not None

    ws = db_session.query(LegacyWorkspace).filter(LegacyWorkspace.slug == "engineering").first()
    assert ws is not None

    # Check default compute created for this workspace
    computes = db_session.query(ComputeResource).filter(ComputeResource.workspace_id == ws.id).all()
    assert len(computes) == 1
    assert computes[0].name == "default"
    assert computes[0].runtime == "duckdb"
    assert computes[0].is_default is True
    assert computes[0].desired_status == "running"

    # Check default warehouse created for this workspace
    warehouses = db_session.query(SqlWarehouse).filter(SqlWarehouse.workspace_id == ws.id).all()
    assert len(warehouses) == 1
    assert warehouses[0].name == "default"
    assert warehouses[0].engine == "duckdb"
    assert warehouses[0].status == "running"


def test_ensure_workspace_default_resources_starts_runtime_with_runtime_manager(db_session: Session):
    """Test that ensure_workspace_default_resources invokes runtime_manager to start the DuckDB compute."""
    from unittest.mock import AsyncMock
    from compassx.models import RuntimeNotFoundError, RuntimeInfo, RuntimePhase

    ws_id = str(uuid4())

    mock_rm = MagicMock()
    mock_rm.start_runtime = AsyncMock(side_effect=RuntimeNotFoundError("Not found"))
    mock_rm.create_runtime = AsyncMock(return_value=RuntimeInfo(
        runtime_id="rt-1",
        runtime_type="duckdb",
        phase=RuntimePhase.RUNNING,
    ))

    result = ensure_workspace_default_resources(
        system_db=db_session,
        workspace_id=ws_id,
        created_by="user-admin",
        user_id="user-admin",
        runtime_manager=mock_rm,
    )

    assert result["compute_created"] is True
    assert mock_rm.create_runtime.called
    call_args = mock_rm.create_runtime.call_args
    assert call_args[0][0] == "duckdb"


