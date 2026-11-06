"""User Manager — workspace member management routes (§5.3, §7.3).

GET    /api/um/workspaces/{workspace_id}/members
POST   /api/um/workspaces/{workspace_id}/members/invite
DELETE /api/um/workspaces/{workspace_id}/members/{user_id}
PATCH  /api/um/workspaces/{workspace_id}/members/{user_id}/role
POST   /api/um/workspaces/{workspace_id}/set-default
"""

from __future__ import annotations

import logging

import secrets

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.database import get_account_db, get_system_db

from app.user_manager.audit import log_action

from app.user_manager.auth_utils import hash_refresh_token

from app.user_manager.cross_db import assert_workspace_exists_in_account_db

from app.user_manager.dependencies import (
    get_current_um_user, get_effective_account_role, get_effective_workspace_role,
    require_workspace_admin,
)

from app.user_manager.entry_point import invalidate_entry_point_cache

from app.user_manager.models.account_models import (
    UmUser, UmInvite, UmGroup, UmServicePrincipal, UmAccountRoleAssignment,
)

from app.user_manager.models.system_models import UmWorkspaceRoleAssignment, UmWorkspaceRole, UmPrincipalType

logger = logging.getLogger("app.user_manager.routes.workspace_member_routes")

router = APIRouter(prefix="/api/um/workspaces", tags=["um-workspace-members"])

class MemberOut(BaseModel):
    assignment_id: str
    principal_id: str
    user_id: str | None = None
    group_id: str | None = None
    sp_id: str | None = None
    principal_type: str
    email: str | None = None
    display_name: str | None = None
    client_id: str | None = None
    member_count: int | None = None
    role_id: str
    is_default: bool
    granted_at: datetime

class CandidatePrincipalOut(BaseModel):
    id: str
    type: str  # "user" | "group" | "service_principal"
    display_name: str
    email_or_client_id: str | None = None
    details: str | None = None

class AssignPrincipalIn(BaseModel):
    principal_id: str
    principal_type: str  # "user" | "group" | "service_principal"
    role_id: str = "analyst"

class InviteOrAddIn(BaseModel):
    email_or_user_id: str
    role_id: str

class WorkspaceUserCreateIn(BaseModel):
    email: str
    display_name: str
    password: str
    role_id: str = "analyst"

class RolePatch(BaseModel):
    role_id: str

def _require_ws_admin(workspace_id: str, user: UmUser, account_db: Session, system_db: Session):
    require_workspace_admin(workspace_id, user, account_db, system_db)

def _valid_ws_role(role_id: str, system_db: Session) -> None:
    if not system_db.get(UmWorkspaceRole, role_id):
        raise HTTPException(status_code=400, detail=f"Unknown workspace role: {role_id}")
