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

from app.config import settings

logger = logging.getLogger("app.workspace.account_routes")

router = APIRouter(prefix="/api/account", tags=["account-admin"])

DEFAULT_ACCOUNT_SETTINGS = {
    "airflow": {
        "webserver_enabled": False,
        "tuning_profile": "cost_optimized",
        "dag_dir_list_interval": 300,
        "min_file_process_interval": 120,
        "parsing_processes": 2,
    },
    "app_node_pool": {
        "dedicated_pool_enabled": False,
        "pool_name": "apppool",
        "default_pool_name": "systempoolv2",
        "vm_size": "Standard_B2s_v2",
        "min_count": 1,
        "max_count": 5,
        "auto_scale": True,
    },
    "compute": {
        "auto_stop_enabled": True,
        "auto_stop_minutes": 5,
        "dedicated_pool_enabled": True,
        "pool_name": "computepool",
        "vm_size": "Standard_D4ads_v5",
        "min_count": 0,
        "max_count": 10,
        "auto_scale": True,
        "is_provisioned": True,
    },
}

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

import app.workspace.http.account.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.workspace.http.account.application.get_account import get_account as get_account_action
from app.workspace.http.account.application.patch_account import patch_account as patch_account_action
from app.workspace.http.account.application.get_account_settings import get_account_settings as get_account_settings_action
from app.workspace.http.account.application.update_account_settings import update_account_settings as update_account_settings_action
from app.workspace.http.account.application.trigger_nodepool_switchover import trigger_nodepool_switchover as trigger_nodepool_switchover_action
from app.workspace.http.account.application.get_nodepool_status import get_nodepool_status as get_nodepool_status_action
from app.workspace.http.account.application.trigger_compute_provision import trigger_compute_provision as trigger_compute_provision_action
from app.workspace.http.account.application.trigger_compute_deprovision import trigger_compute_deprovision as trigger_compute_deprovision_action
from app.workspace.http.account.application.trigger_compute_switchover import trigger_compute_switchover as trigger_compute_switchover_action
from app.workspace.http.account.application.get_compute_status import get_compute_status as get_compute_status_action
from app.workspace.http.account.application.list_workspaces import list_workspaces as list_workspaces_action
from app.workspace.http.account.application.create_workspace import create_workspace as create_workspace_action
from app.workspace.http.account.application.get_workspace import get_workspace as get_workspace_action
from app.workspace.http.account.application.update_workspace import update_workspace as update_workspace_action
from app.workspace.http.account.application.delete_workspace import delete_workspace as delete_workspace_action
from app.workspace.http.account.application.list_principals import list_principals as list_principals_action
from app.workspace.http.account.application.create_principal import create_principal as create_principal_action
from app.workspace.http.account.application.update_principal import update_principal as update_principal_action
from app.workspace.http.account.application.deactivate_principal import deactivate_principal as deactivate_principal_action
from app.workspace.http.account.application.reset_password import reset_password as reset_password_action

router = APIRouter(prefix="/api/account", tags=["account-admin"])


@router.get("", response_model=AccountOut)
def get_account(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return get_account_action(db=db, _admin=_admin)


@router.patch("", response_model=AccountOut)
def patch_account(
    body: AccountPatch,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return patch_account_action(body=body, db=db, _admin=_admin)


@router.get("/settings")
def get_account_settings(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return get_account_settings_action(db=db, _admin=_admin)


@router.patch("/settings")
def update_account_settings(
    body: dict,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return update_account_settings_action(body=body, db=db, _admin=_admin)


@router.post("/settings/nodepool/switchover")
def trigger_nodepool_switchover(
    target_pool: Optional[str] = None,
    _admin: Principal = Depends(require_account_admin),
):
    """Trigger manual/forced rolling switchover of all app pods to the target node pool."""
    return trigger_nodepool_switchover_action(target_pool=target_pool, _admin=_admin)


@router.get("/settings/nodepool/status")
def get_nodepool_status(
    _admin: Principal = Depends(require_account_admin),
):
    """Return live node pool status, cluster pools, and app workloads."""
    return get_nodepool_status_action(_admin=_admin)


@router.post("/settings/compute/provision")
def trigger_compute_provision(
    body: Optional[dict] = None,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    """Explicitly provision or update compute node pool."""
    return trigger_compute_provision_action(body=body, db=db, _admin=_admin)


@router.post("/settings/compute/deprovision")
def trigger_compute_deprovision(
    body: Optional[dict] = None,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    """Gracefully migrate compute pods to shared user pool and deprovision compute node pool."""
    return trigger_compute_deprovision_action(body=body, db=db, _admin=_admin)


@router.post("/settings/compute/switchover")
def trigger_compute_switchover(
    target_pool: Optional[str] = None,
    _admin: Principal = Depends(require_account_admin),
):
    """Trigger manual rolling switchover of all compute and notebook pods to the target node pool."""
    return trigger_compute_switchover_action(target_pool=target_pool, _admin=_admin)


@router.get("/settings/compute/status")
def get_compute_status(
    _admin: Principal = Depends(require_account_admin),
):
    """Return live compute node pool status, cluster pools, and compute workloads."""
    return get_compute_status_action(_admin=_admin)


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return list_workspaces_action(db=db, _admin=_admin)


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
    request: Request = None,
):
    return await create_workspace_action(body=body, db=db, admin=admin, request=request)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return get_workspace_action(workspace_id=workspace_id, db=db, _admin=_admin)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    body: WorkspacePatch,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return update_workspace_action(workspace_id=workspace_id, body=body, db=db, _admin=_admin)


@router.delete("/workspaces/{workspace_id}", status_code=202)
def delete_workspace(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return delete_workspace_action(workspace_id=workspace_id, background_tasks=background_tasks, db=db, _admin=_admin)


@router.get("/principals", response_model=list[PrincipalOut])
def list_principals(
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return list_principals_action(db=db, admin=admin)


@router.post("/principals", response_model=PrincipalOut, status_code=201)
def create_principal(
    body: PrincipalCreate,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return create_principal_action(body=body, db=db, admin=admin)


@router.patch("/principals/{principal_id}", response_model=PrincipalOut)
def update_principal(
    principal_id: str,
    body: PrincipalPatch,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return update_principal_action(principal_id=principal_id, body=body, db=db, admin=admin)


@router.delete("/principals/{principal_id}", status_code=204)
def deactivate_principal(
    principal_id: str,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return deactivate_principal_action(principal_id=principal_id, db=db, admin=admin)


@router.post("/principals/{principal_id}/reset-password", status_code=204)
def reset_password(
    principal_id: str,
    body: PasswordResetRequest,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return reset_password_action(principal_id=principal_id, body=body, db=db, admin=admin)
