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

import app.user_manager.http.members.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.user_manager.http.members.application.list_workspace_members import list_workspace_members as list_workspace_members_action
from app.user_manager.http.members.application.list_candidate_principals import list_candidate_principals as list_candidate_principals_action
from app.user_manager.http.members.application.assign_principal_to_workspace import assign_principal_to_workspace as assign_principal_to_workspace_action
from app.user_manager.http.members.application.invite_or_add_member import invite_or_add_member as invite_or_add_member_action
from app.user_manager.http.members.application.create_workspace_user import create_workspace_user as create_workspace_user_action
from app.user_manager.http.members.application.update_member_role import update_member_role as update_member_role_action
from app.user_manager.http.members.application.remove_workspace_member import remove_workspace_member as remove_workspace_member_action
from app.user_manager.http.members.application.set_default_workspace import set_default_workspace as set_default_workspace_action

router = APIRouter(prefix="/api/um/workspaces", tags=["um-workspace-members"])


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_workspace_members(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    return list_workspace_members_action(workspace_id=workspace_id, user=user, account_db=account_db, system_db=system_db)


@router.get("/{workspace_id}/candidate-principals", response_model=list[CandidatePrincipalOut])
def list_candidate_principals(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Return all account-level users, groups, and service principals NOT yet assigned to this workspace."""
    return list_candidate_principals_action(workspace_id=workspace_id, user=user, account_db=account_db, system_db=system_db)


@router.post("/{workspace_id}/members/assign", status_code=201)
def assign_principal_to_workspace(
    workspace_id: str,
    body: AssignPrincipalIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Assign an existing Account User, Group, or Service Principal to a workspace."""
    return assign_principal_to_workspace_action(workspace_id=workspace_id, body=body, user=user, account_db=account_db, system_db=system_db)


@router.post("/{workspace_id}/members/invite", status_code=201)
def invite_or_add_member(
    workspace_id: str,
    body: InviteOrAddIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """grant_workspace_access per §5.3.
    
    If email_or_user_id matches an existing user → add directly.
    If no user found → create a workspace-scoped invite.
    """
    return invite_or_add_member_action(workspace_id=workspace_id, body=body, user=user, account_db=account_db, system_db=system_db)


@router.post("/{workspace_id}/members/create", status_code=201)
def create_workspace_user(
    workspace_id: str,
    body: WorkspaceUserCreateIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Directly provision a new user and add them to the workspace in one step."""
    return create_workspace_user_action(workspace_id=workspace_id, body=body, user=user, account_db=account_db, system_db=system_db)


@router.patch("/{workspace_id}/members/{principal_id}/role", status_code=200)
def update_member_role(
    workspace_id: str,
    principal_id: str,
    body: RolePatch,
    actor: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    return update_member_role_action(workspace_id=workspace_id, principal_id=principal_id, body=body, actor=actor, account_db=account_db, system_db=system_db)


@router.delete("/{workspace_id}/members/{principal_id}", status_code=200)
def remove_workspace_member(
    workspace_id: str,
    principal_id: str,
    actor: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    return remove_workspace_member_action(workspace_id=workspace_id, principal_id=principal_id, actor=actor, account_db=account_db, system_db=system_db)


@router.post("/{workspace_id}/set-default", status_code=200)
def set_default_workspace(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    system_db: Session = Depends(get_system_db),
    account_db: Session = Depends(get_account_db),
):
    """Set is_default=true for this workspace for the current user (§5.6)."""
    return set_default_workspace_action(workspace_id=workspace_id, user=user, system_db=system_db, account_db=account_db)
