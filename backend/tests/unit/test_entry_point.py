from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import AccountBase, SystemBase
from app.workspace.models import Account, Workspace
from app.user_manager.models.account_models import UmUser, UmAccountRoleAssignment
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
