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
