from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import AccountBase, SystemBase
from app.workspace.models import Account, Workspace
from app.user_manager.models.account_models import UmUser, UmAccountRoleAssignment
from app.user_manager.models.system_models import UmWorkspaceRole, UmWorkspaceRoleAssignment
from app.user_manager.entry_point import resolve_entry_point, invalidate_entry_point_cache


@pytest.fixture
def test_dbs():
    engine_account = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine_system = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    AccountBase.metadata.create_all(engine_account)
    SystemBase.metadata.create_all(engine_system)

    SessionAccount = sessionmaker(bind=engine_account)
    SessionSystem = sessionmaker(bind=engine_system)

    account_db = SessionAccount()
    system_db = SessionSystem()

    yield account_db, system_db

    account_db.close()
    system_db.close()
    AccountBase.metadata.drop_all(engine_account)
    SystemBase.metadata.drop_all(engine_system)


def test_resolve_entry_point_account_admin_zero_workspaces(test_dbs):
    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())

    # Create account and admin user
    account = Account(id=acc_id, name="Test Account", slug="test-acc")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="admin@test.com", password_hash="hash")
    account_db.add(user)
    account_db.flush()

    # Assign account_admin role
    admin_role = UmAccountRoleAssignment(
        account_id=acc_id,
        principal_id=user_id,
        principal_type="user",
        role_id="account_admin",
    )
    account_db.add(admin_role)
    account_db.commit()

    # No workspaces exist in DB
    result = resolve_entry_point(user_id, account_db, system_db)
    assert result["workspace_id"] is None
    assert result["section"] == "create_workspace"
    assert result["route"] == "/workspace/create"


def test_resolve_entry_point_regular_user_zero_workspaces(test_dbs):
    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())

    # Create account and regular user
    account = Account(id=acc_id, name="Test Account 2", slug="test-acc-2")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="member@test.com", password_hash="hash")
    account_db.add(user)
    account_db.flush()

    # Assign member role (not admin)
    member_role = UmAccountRoleAssignment(
        account_id=acc_id,
        principal_id=user_id,
        principal_type="user",
        role_id="member",
    )
    account_db.add(member_role)
    account_db.commit()

    # No workspaces exist in DB
    result = resolve_entry_point(user_id, account_db, system_db)
    assert result["workspace_id"] is None
    assert result["section"] == "none"
    assert result["route"] == "/no-workspace-access"


def test_resolve_entry_point_account_admin_with_workspace(test_dbs):
    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())
    ws_id = str(uuid4())

    # Create account, user, and workspace
    account = Account(id=acc_id, name="Test Account 3", slug="test-acc-3")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="admin3@test.com", password_hash="hash")
    account_db.add(user)
    account_db.flush()

    ws = Workspace(
        id=ws_id,
        account_id=acc_id,
        name="Engineering",
        slug="engineering",
        storage_backend="minio",
        storage_config={},
        status="active",
        created_by=user_id,
    )
    account_db.add(ws)
    account_db.flush()

    # Assign account_admin role
    admin_role = UmAccountRoleAssignment(
        account_id=acc_id,
        principal_id=user_id,
        principal_type="user",
        role_id="account_admin",
    )
    account_db.add(admin_role)
    account_db.commit()

    result = resolve_entry_point(user_id, account_db, system_db)
    assert result["workspace_id"] == ws_id
    assert result["section"] == "app"
    assert result["route"] == "/w/engineering/platform/notebooks"


def test_resolve_entry_point_multiple_workspaces_no_default(test_dbs):
    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())
    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    account = Account(id=acc_id, name="Test Multi WS", slug="test-multi-ws")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="user@test.com", password_hash="hash")
    account_db.add(user)

    ws1 = Workspace(id=ws1_id, account_id=acc_id, name="WS 1", slug="ws-1", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    ws2 = Workspace(id=ws2_id, account_id=acc_id, name="WS 2", slug="ws-2", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    account_db.add_all([ws1, ws2])
    account_db.commit()

    # Seed roles
    role = UmWorkspaceRole(id="analyst", display_name="Analyst")
    system_db.merge(role)
    system_db.flush()

    wra1 = UmWorkspaceRoleAssignment(
        workspace_id=ws1_id,
        principal_id=user_id,
        principal_type="user",
        role_id="analyst",
        is_default=False,
    )
    wra2 = UmWorkspaceRoleAssignment(
        workspace_id=ws2_id,
        principal_id=user_id,
        principal_type="user",
        role_id="analyst",
        is_default=False,
    )
    system_db.add_all([wra1, wra2])
    system_db.commit()

    result = resolve_entry_point(user_id, account_db, system_db)
    assert result["workspace_id"] is None
    assert result["section"] == "picker"
    assert result["route"] == "/workspace-picker"


def test_resolve_entry_point_multiple_workspaces_with_default(test_dbs):
    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())
    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    account = Account(id=acc_id, name="Test Default WS", slug="test-default-ws")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="user2@test.com", password_hash="hash")
    account_db.add(user)

    ws1 = Workspace(id=ws1_id, account_id=acc_id, name="WS 1", slug="ws-1", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    ws2 = Workspace(id=ws2_id, account_id=acc_id, name="Marketing", slug="marketing", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    account_db.add_all([ws1, ws2])
    account_db.commit()

    role = UmWorkspaceRole(id="business_viewer", display_name="Viewer")
    system_db.merge(role)
    system_db.flush()

    # ws2 is default
    wra1 = UmWorkspaceRoleAssignment(
        workspace_id=ws1_id,
        principal_id=user_id,
        principal_type="user",
        role_id="business_viewer",
        is_default=False,
    )
    wra2 = UmWorkspaceRoleAssignment(
        workspace_id=ws2_id,
        principal_id=user_id,
        principal_type="user",
        role_id="business_viewer",
        is_default=True,
    )
    system_db.add_all([wra1, wra2])
    system_db.commit()

    result = resolve_entry_point(user_id, account_db, system_db)
    assert result["workspace_id"] == ws2_id
    assert result["section"] == "app"
    assert result["route"] == "/w/marketing/platform/notebooks"


def test_resolve_entry_point_deep_link(test_dbs):
    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())
    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    account = Account(id=acc_id, name="Test DeepLink", slug="test-dl")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="dl@test.com", password_hash="hash")
    account_db.add(user)

    ws1 = Workspace(id=ws1_id, account_id=acc_id, name="WS 1", slug="ws-1", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    ws2 = Workspace(id=ws2_id, account_id=acc_id, name="WS 2", slug="ws-2", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    account_db.add_all([ws1, ws2])
    account_db.commit()

    role = UmWorkspaceRole(id="analyst", display_name="Analyst")
    system_db.merge(role)
    system_db.flush()

    wra1 = UmWorkspaceRoleAssignment(
        workspace_id=ws1_id,
        principal_id=user_id,
        principal_type="user",
        role_id="analyst",
        is_default=True,  # ws1 is default
    )
    wra2 = UmWorkspaceRoleAssignment(
        workspace_id=ws2_id,
        principal_id=user_id,
        principal_type="user",
        role_id="analyst",
        is_default=False,
    )
    system_db.add_all([wra1, wra2])
    system_db.commit()

    # Deep link by slug
    result_slug = resolve_entry_point(user_id, account_db, system_db, deep_link_workspace_id="ws-2")
    assert result_slug["workspace_id"] == ws2_id
    assert result_slug["route"] == "/w/ws-2/platform/notebooks"

    # Deep link by UUID
    invalidate_entry_point_cache()
    result_uuid = resolve_entry_point(user_id, account_db, system_db, deep_link_workspace_id=ws2_id)
    assert result_uuid["workspace_id"] == ws2_id
    assert result_uuid["route"] == "/w/ws-2/platform/notebooks"


def test_set_default_workspace_flow(test_dbs):
    from app.user_manager.routes.workspace_member_routes import set_default_workspace

    account_db, system_db = test_dbs
    invalidate_entry_point_cache()

    acc_id = str(uuid4())
    user_id = str(uuid4())
    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    account = Account(id=acc_id, name="Test SetDefault", slug="test-set-def")
    account_db.add(account)
    account_db.flush()

    user = UmUser(id=user_id, account_id=acc_id, email="defuser@test.com", password_hash="hash")
    account_db.add(user)

    ws1 = Workspace(id=ws1_id, account_id=acc_id, name="WS 1", slug="ws-1", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    ws2 = Workspace(id=ws2_id, account_id=acc_id, name="Analytics", slug="analytics", status="active", storage_backend="minio", storage_config={}, created_by=user_id)
    account_db.add_all([ws1, ws2])
    account_db.commit()

    role = UmWorkspaceRole(id="analyst", display_name="Analyst")
    system_db.merge(role)
    system_db.flush()

    wra1 = UmWorkspaceRoleAssignment(
        workspace_id=ws1_id,
        principal_id=user_id,
        principal_type="user",
        role_id="analyst",
        is_default=False,
    )
    wra2 = UmWorkspaceRoleAssignment(
        workspace_id=ws2_id,
        principal_id=user_id,
        principal_type="user",
        role_id="analyst",
        is_default=False,
    )
    system_db.add_all([wra1, wra2])
    system_db.commit()

    # Initial state: no default workspace -> returns workspace-picker
    res0 = resolve_entry_point(user_id, account_db, system_db)
    assert res0["section"] == "picker"
    assert res0["route"] == "/workspace-picker"

    # User sets ws2 ("analytics") as default via slug
    set_default_workspace(
        workspace_id="analytics",
        user=user,
        system_db=system_db,
        account_db=account_db,
    )

    # Next resolution -> directly routes to analytics workspace without picker!
    res1 = resolve_entry_point(user_id, account_db, system_db)
    assert res1["workspace_id"] == ws2_id
    assert res1["section"] == "app"
    assert res1["route"] == "/w/analytics/platform/notebooks"

    # Now user switches to ws1 ("ws-1") via ID
    set_default_workspace(
        workspace_id=ws1_id,
        user=user,
        system_db=system_db,
        account_db=account_db,
    )

    # Subsequent resolution -> directly routes to ws-1 workspace!
    res2 = resolve_entry_point(user_id, account_db, system_db)
    assert res2["workspace_id"] == ws1_id
    assert res2["section"] == "app"
    assert res2["route"] == "/w/ws-1/platform/notebooks"


