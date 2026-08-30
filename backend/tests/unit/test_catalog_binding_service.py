import pytest
import asyncio
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy.orm import Session

from app.catalog.binding_service import CatalogBindingService
from app.catalog.schemas import BindingCreate, CatalogPrivilege
from app.catalog.models import UnifiedCatalog, CatalogWorkspaceBinding
from app.catalog.service import list_catalogs, ensure_default_catalog
from app.workspace.models import Workspace, Account, Principal


def test_bind_catalog_auto_creates_and_binds(db_session: Session):
    # Ensure default catalog is loaded/created
    catalog = ensure_default_catalog(db_session)
    assert catalog.name == "compassx"

    account_id = str(uuid4())
    principal_id = str(uuid4())
    workspace_id = str(uuid4())

    # Create account and principal to satisfy foreign key constraints
    account = Account(id=account_id, name="Test Account", slug="testaccount")
    db_session.add(account)
    db_session.commit()

    principal = Principal(
        id=principal_id,
        account_id=account.id,
        type="user",
        name="System",
        email="system@local",
        password_hash="...",
        is_active=True,
    )
    db_session.add(principal)
    db_session.commit()

    # Create a workspace
    ws = Workspace(
        id=workspace_id,
        account_id=account.id,
        name="Test Workspace",
        slug="test-ws",
        storage_backend="local",
        storage_config={},
        created_by=principal.id,
    )
    db_session.add(ws)
    db_session.commit()

    service = CatalogBindingService(db_session)
    binding = asyncio.run(service.bind_catalog(
        workspace_id=ws.id,
        data=BindingCreate(
            catalog_name="compassx",
            privilege=CatalogPrivilege.READ_WRITE,
            is_default=True,
        ),
        bound_by="system",
    ))

    db_session.commit()

    assert binding.workspace_id == ws.id
    assert binding.catalog_id == catalog.id
    assert binding.privilege == "READ_WRITE"
    assert binding.is_default is True
    assert binding.bound_by == "system"


def test_list_catalogs_filtering(db_session: Session):
    # Clear existing catalogs
    db_session.query(CatalogWorkspaceBinding).delete()
    db_session.query(UnifiedCatalog).delete()
    db_session.commit()

    # Create catalogs
    cat1 = UnifiedCatalog(name="compassx", description="Default", created_by="system", all_workspaces=False)
    cat2 = UnifiedCatalog(name="shared_catalog", description="Shared", created_by="system", all_workspaces=True)
    cat3 = UnifiedCatalog(name="secret_catalog", description="Secret", created_by="system", all_workspaces=False)
    
    db_session.add_all([cat1, cat2, cat3])
    db_session.commit()

    account_id = str(uuid4())
    principal_id = str(uuid4())
    ws1_id = str(uuid4())
    ws2_id = str(uuid4())

    # Create account and principal
    account = Account(id=account_id, name="Test Account", slug="testaccount2")
    db_session.add(account)
    db_session.commit()

    principal = Principal(
        id=principal_id,
        account_id=account.id,
        type="user",
        name="System",
        email="system@local",
        password_hash="...",
        is_active=True,
    )
    db_session.add(principal)
    db_session.commit()

    # Create workspaces
    ws1 = Workspace(id=ws1_id, account_id=account.id, name="WS 1", slug="ws1", storage_backend="local", storage_config={}, created_by=principal.id)
    ws2 = Workspace(id=ws2_id, account_id=account.id, name="WS 2", slug="ws2", storage_backend="local", storage_config={}, created_by=principal.id)
    db_session.add_all([ws1, ws2])
    db_session.commit()

    # Bind cat1 to ws1
    bind1 = CatalogWorkspaceBinding(
        catalog_id=cat1.id,
        workspace_id=ws1_id,
        privilege="READ_WRITE",
        is_default=True,
        bound_by="system",
    )
    db_session.add(bind1)
    db_session.commit()

    # List catalogs with no workspace_id (admin / global view)
    all_cats = list_catalogs(db_session)
    assert len(all_cats) == 3

    # List catalogs for ws1: should see compassx (explicitly bound) and shared_catalog (all_workspaces=True)
    ws1_cats = list_catalogs(db_session, workspace_id=ws1_id)
    cat_names = {c.name for c in ws1_cats}
    assert "compassx" in cat_names
    assert "shared_catalog" in cat_names
    assert "secret_catalog" not in cat_names

    # List catalogs for ws2: should only see shared_catalog (all_workspaces=True)
    ws2_cats = list_catalogs(db_session, workspace_id=ws2_id)
    cat_names_2 = {c.name for c in ws2_cats}
    assert "shared_catalog" in cat_names_2
    assert "compassx" not in cat_names_2
    assert "secret_catalog" not in cat_names_2


def test_add_catalog_auto_binds(db_session: Session):
    from unittest.mock import MagicMock
    from app.catalog.routes import add_catalog
    from app.catalog.schemas import CatalogCreate
    
    account_id = str(uuid4())
    principal_id = str(uuid4())
    workspace_id = str(uuid4())

    # Create account, principal and workspace in database
    account = Account(id=account_id, name="Test Account", slug="acc123")
    db_session.add(account)
    db_session.commit()

    principal = Principal(
        id=principal_id,
        account_id=account.id,
        type="user",
        name="System",
        email="system@local",
        password_hash="...",
        is_active=True,
    )
    db_session.add(principal)
    db_session.commit()

    ws = Workspace(
        id=workspace_id,
        account_id=account.id,
        name="WS 1",
        slug="ws123",
        storage_backend="local",
        storage_config={},
        created_by=principal.id,
    )
    db_session.add(ws)
    db_session.commit()

    # Mock Request
    request = MagicMock()
    # Mock request.state.workspace
    class MockWorkspaceContext:
        def __init__(self, workspace_id):
            self.workspace_id = workspace_id
    request.state.workspace = MockWorkspaceContext(workspace_id)

    body = CatalogCreate(
        name="test_auto_bind_catalog",
        description="Auto bind test",
        catalog_type="postgres",
        connection_id=None,
        database_name=None,
    )

    user = {"email": "system@local", "id": principal_id}

    # This test is about auto-binding, not access control, and calling the
    # handler directly bypasses dependency injection — so supply a guard that
    # allows the create. Enforcement itself is covered by the governance suite.
    guard = MagicMock()
    guard.require_workspace_admin.return_value = None
    guard.claim_ownership.return_value = None

    # Call the router function
    catalog = add_catalog(request, body, db_session, user, guard)

    # Check that a binding was created
    binding = db_session.query(CatalogWorkspaceBinding).filter(
        CatalogWorkspaceBinding.catalog_id == catalog.id,
        CatalogWorkspaceBinding.workspace_id == workspace_id
    ).first()

    assert binding is not None
    assert binding.privilege == "READ_WRITE"
    assert binding.is_default is False


@patch("app.workspace.account_routes.validate_storage_config")
def test_create_workspace_auto_creates_custom_catalog(mock_validate, db_session: Session):
    from app.workspace.account_routes import create_workspace
    from app.workspace.schemas import WorkspaceCreate
    
    # Setup account and principal
    account = Account(id=str(uuid4()), name="Test Account", slug="testaccount")
    db_session.add(account)
    db_session.commit()

    principal = Principal(
        id=str(uuid4()),
        account_id=account.id,
        type="user",
        name="System",
        email="system@local",
        password_hash="...",
        is_active=True,
    )
    db_session.add(principal)
    db_session.commit()

    body = WorkspaceCreate(
        name="Engineering Workspace Team",
        slug="eng-ws-team",
        storage_backend="minio",
        storage_config={},
    )

    # Call route function (it's async, so run via asyncio.run)
    ws_out = asyncio.run(create_workspace(body, db_session, principal))

    # Verify workspace was created
    assert ws_out.slug == "eng-ws-team"

    # Verify custom catalog was created: engineering_workspace_team_default
    catalog = db_session.query(UnifiedCatalog).filter(
        UnifiedCatalog.name == "engineering_workspace_team_default"
    ).first()

    assert catalog is not None
    assert catalog.catalog_type == "iceberg"

    # Verify catalog is bound to the workspace
    binding = db_session.query(CatalogWorkspaceBinding).filter(
        CatalogWorkspaceBinding.catalog_id == catalog.id,
        CatalogWorkspaceBinding.workspace_id == ws_out.id
    ).first()

    assert binding is not None
    assert binding.privilege == "READ_WRITE"
    assert binding.is_default is True
