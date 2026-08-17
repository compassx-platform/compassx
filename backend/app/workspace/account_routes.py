"""Account admin APIs: account info, workspace CRUD, principal CRUD.

All endpoints require account admin token.
"""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.workspace.auth import hash_password, require_account_admin
from app.workspace.models import (
    Account,
    CatalogObject,
    Principal,
    Workspace,
    WorkspaceMembership,
)
from app.workspace.schemas import (
    AccountOut,
    AccountPatch,
    MemberAdd,
    PasswordResetRequest,
    PrincipalCreate,
    PrincipalOut,
    PrincipalPatch,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspacePatch,
)
from app.workspace.storage_validator import validate_storage_config, encrypt_storage_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["account-admin"])


# ── Account ──────────────────────────────────────────────────────────────────

@router.get("", response_model=AccountOut)
def get_account(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    account = db.query(Account).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("", response_model=AccountOut)
def patch_account(
    body: AccountPatch,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    account = db.query(Account).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    account.name = body.name
    db.commit()
    db.refresh(account)
    return account


# ── Workspaces ───────────────────────────────────────────────────────────────

@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return [
        WorkspaceOut(
            id=w.id, name=w.name, slug=w.slug, status=w.status,
            storage_backend=w.storage_backend,
            url=f"/w/{w.slug}",
            created_at=w.created_at,
        )
        for w in db.query(Workspace).all()
    ]


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    # Validate slug uniqueness
    if db.query(Workspace).filter(Workspace.slug == body.slug).first():
        raise HTTPException(status_code=400, detail="Workspace slug already exists")

    # Validate storage config (test blob write)
    try:
        validate_storage_config(body.storage_backend, body.storage_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Encrypt sensitive fields
    encrypted_config = encrypt_storage_config(body.storage_config)

    ws_id = str(uuid4())
    ws = Workspace(
        id=ws_id,
        account_id=admin.account_id,
        name=body.name,
        slug=body.slug,
        storage_backend=body.storage_backend,
        storage_config=encrypted_config,
        created_by=admin.id,
    )
    db.add(ws)
    db.flush()

    # Auto-add creating admin as workspace admin member
    db.add(WorkspaceMembership(
        workspace_id=ws_id,
        principal_id=admin.id,
        role="admin",
        granted_by=admin.id,
    ))

    # Also add UmWorkspaceRoleAssignment in system_db (User Manager v1 topology)
    try:
        from app.database import SystemSessionLocal
        if SystemSessionLocal:
            sys_db = SystemSessionLocal()
            try:
                from app.user_manager.models.system_models import UmWorkspaceRoleAssignment
                sys_db.add(UmWorkspaceRoleAssignment(
                    workspace_id=ws_id,
                    principal_id=admin.id,
                    principal_type="user",
                    role_id="workspace_admin",
                    is_default=True,
                    granted_by=admin.id,
                ))
                sys_db.commit()
            finally:
                sys_db.close()
    except Exception as sys_err:
        logger.warning("Could not add system workspace role assignment: %s", sys_err)

    # Auto-create and bind workspace-specific default catalog
    try:
        import re
        from app.catalog.binding_service import CatalogBindingService
        from app.catalog.schemas import BindingCreate, CatalogPrivilege
        from app.catalog.models import UnifiedCatalog
        
        # Normalize workspace name to valid catalog name
        normalized_name = ws.name.lower().replace(" ", "_").replace("-", "_")
        normalized_name = re.sub(r'[^a-z0-9_]', '', normalized_name)
        if not normalized_name:
            normalized_name = "workspace"
        catalog_name = f"{normalized_name}_default"
        
        # Check if catalog already exists
        catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
        if not catalog:
            catalog = UnifiedCatalog(
                name=catalog_name,
                description=f"Default catalog for workspace {ws.name}",
                catalog_type="iceberg",
                created_by="system",
            )
            db.add(catalog)
            db.flush()

        binding_service = CatalogBindingService(db)
        await binding_service.bind_catalog(
            workspace_id=ws_id,
            data=BindingCreate(
                catalog_name=catalog_name,
                privilege=CatalogPrivilege.READ_WRITE,
                is_default=True,
            ),
            bound_by="system",
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workspace due to catalog creation/binding error: {exc}"
        )
    db.refresh(ws)

    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, status=ws.status,
        storage_backend=ws.storage_backend,
        url=f"/w/{ws.slug}",
        created_at=ws.created_at,
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, status=ws.status,
        storage_backend=ws.storage_backend,
        url=f"/w/{ws.slug}",
        created_at=ws.created_at,
    )


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    body: WorkspacePatch,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if body.name is not None:
        ws.name = body.name
    if body.storage_config is not None:
        ws.storage_config = encrypt_storage_config(body.storage_config)
    db.commit()
    db.refresh(ws)
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, status=ws.status,
        storage_backend=ws.storage_backend,
        url=f"/w/{ws.slug}",
        created_at=ws.created_at,
    )


@router.delete("/workspaces/{workspace_id}", status_code=202)
def delete_workspace(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.status = "deleting"
    db.commit()
    background_tasks.add_task(_purge_workspace, workspace_id)
    return {"status": "accepted", "workspace_id": workspace_id}


def _purge_workspace(workspace_id: str) -> None:
    """Background job: purge workspace data then hard-delete workspace row."""
    from app.database import AccountSessionLocal, SystemSessionLocal
    from app.workspace.data_models import (
        WpSession, WpSqlWarehouse, WpLlmCallLog, AgentRunLog, AgentTurnLog,
        QueryHistory, SrmMemory,
    )

    if SystemSessionLocal:
        data_db = SystemSessionLocal()
        try:
            for model in [WpSession, WpSqlWarehouse, SrmMemory]:
                data_db.query(model).filter(model.workspace_id == workspace_id).delete()
            data_db.commit()
        except Exception:
            logger.exception("Error purging data plane for workspace %s", workspace_id)
        finally:
            data_db.close()

    if AccountSessionLocal:
        sys_db = AccountSessionLocal()
        try:
            # Delete workspace-scoped catalog objects
            from app.workspace.models import CatalogObject as CatObj
            sys_db.query(CatObj).filter(
                CatObj.home_workspace_id == workspace_id,
                CatObj.visibility == "workspace",
            ).delete()
            # Transfer global objects (ownership to account admin) - set home_workspace_id=None already done
            # Delete memberships (cascade)
            ws = sys_db.query(Workspace).filter(Workspace.id == workspace_id).first()
            if ws:
                sys_db.delete(ws)
            sys_db.commit()
            logger.info("Workspace %s purged and deleted", workspace_id)
        except Exception:
            logger.exception("Error hard-deleting workspace %s", workspace_id)
        finally:
            sys_db.close()


# ── Principals ───────────────────────────────────────────────────────────────

@router.get("/principals", response_model=list[PrincipalOut])
def list_principals(
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return db.query(Principal).filter(Principal.account_id == admin.account_id).all()


@router.post("/principals", response_model=PrincipalOut, status_code=201)
def create_principal(
    body: PrincipalCreate,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    if body.type not in ("user", "group", "service_principal"):
        raise HTTPException(status_code=400, detail="Invalid principal type")
    if body.email:
        existing = db.query(Principal).filter(
            Principal.account_id == admin.account_id,
            Principal.email == body.email,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists in this account")

    pw_hash = hash_password(body.password) if body.password else None
    p = Principal(
        id=str(uuid4()),
        account_id=admin.account_id,
        type=body.type,
        email=body.email,
        name=body.name,
        password_hash=pw_hash,
        is_account_admin=body.is_account_admin,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch("/principals/{principal_id}", response_model=PrincipalOut)
def update_principal(
    principal_id: str,
    body: PrincipalPatch,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    p = db.query(Principal).filter(
        Principal.id == principal_id,
        Principal.account_id == admin.account_id,
    ).first()
    if p is None:
        raise HTTPException(status_code=404, detail="Principal not found")
    if body.name is not None:
        p.name = body.name
    if body.is_account_admin is not None:
        p.is_account_admin = body.is_account_admin
    if body.is_active is not None:
        p.is_active = body.is_active
    db.commit()
    db.refresh(p)
    return p


@router.delete("/principals/{principal_id}", status_code=204)
def deactivate_principal(
    principal_id: str,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    p = db.query(Principal).filter(
        Principal.id == principal_id,
        Principal.account_id == admin.account_id,
    ).first()
    if p is None:
        raise HTTPException(status_code=404, detail="Principal not found")
    p.is_active = False
    db.commit()


@router.post("/principals/{principal_id}/reset-password", status_code=204)
def reset_password(
    principal_id: str,
    body: PasswordResetRequest,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    p = db.query(Principal).filter(
        Principal.id == principal_id,
        Principal.account_id == admin.account_id,
    ).first()
    if p is None:
        raise HTTPException(status_code=404, detail="Principal not found")
    p.password_hash = hash_password(body.new_password)
    db.commit()
