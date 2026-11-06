"""User Manager — account admin routes (§5.3–5.7, §7.2).

All endpoints require account_admin.
"""

from __future__ import annotations

import logging

import secrets

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.config import settings

from app.database import get_account_db, get_system_db

from app.user_manager.audit import log_action

from app.user_manager.auth_utils import hash_password, generate_refresh_token, hash_refresh_token

from app.user_manager.cross_db import assert_workspace_exists_in_account_db

from app.user_manager.dependencies import (
    get_current_um_user, require_um_account_admin,
    get_effective_account_role,
)

from app.user_manager.entry_point import invalidate_entry_point_cache

from app.user_manager.models.account_models import (
    UmUser, UmRefreshToken, UmAccountRoleAssignment,
    UmGroup, UmGroupMember, UmInvite, UmAuditLog,
    UmServicePrincipal, UmServicePrincipalSecret,
    UmGroupNesting, UmGroupManager, UmServicePrincipalACL,
)

from app.user_manager.models.system_models import UmWorkspaceRoleAssignment

logger = logging.getLogger("app.user_manager.routes.account_routes")

router = APIRouter(prefix="/api/um/account", tags=["um-account"])

class UserListItem(BaseModel):
    id: str
    email: str
    display_name: str | None
    status: str
    account_role: str | None
    workspace_count: int
    last_login_at: datetime | None
    created_at: datetime

class InviteIn(BaseModel):
    email: str
    target_scope: str               # 'account' | 'workspace'
    target_workspace_id: str | None = None
    proposed_account_role_id: str | None = None
    proposed_workspace_role_id: str | None = None

class InviteOut(BaseModel):
    id: str
    email: str
    target_scope: str
    target_workspace_id: str | None
    proposed_account_role_id: str | None
    proposed_workspace_role_id: str | None
    status: str
    expires_at: datetime
    created_at: datetime
    invite_url: str   # stub — in production this is emailed

class GroupOut(BaseModel):
    id: str
    name: str
    source: str
    member_count: int
    created_at: datetime

class GroupMemberOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    added_at: datetime

class AuditLogItem(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    target_type: str
    target_id: str | None
    workspace_id: str | None
    metadata: dict | None
    created_at: datetime

class RolePatch(BaseModel):
    role_id: str

class UserCreateIn(BaseModel):
    email: str
    display_name: str
    password: str
    account_role: str = "account_viewer"

def _invite_to_out(invite: UmInvite, frontend_origin: str, raw_token: str | None = None) -> InviteOut:
    url = f"{frontend_origin}/invite/{raw_token}" if raw_token else f"{frontend_origin}/invite/[token]"
    return InviteOut(
        id=invite.id,
        email=invite.email,
        target_scope=invite.target_scope,
        target_workspace_id=invite.target_workspace_id,
        proposed_account_role_id=invite.proposed_account_role_id,
        proposed_workspace_role_id=invite.proposed_workspace_role_id,
        status=invite.status,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        invite_url=url,
    )

class GroupCreate(BaseModel):
    name: str

class GroupMemberAdd(BaseModel):
    user_id: str

class WorkspaceAdminOut(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    member_count: int
    created_at: datetime

class ServicePrincipalCreate(BaseModel):
    display_name: str

class ServicePrincipalPatch(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None

class ServicePrincipalOut(BaseModel):
    id: str
    account_id: str
    application_id: str
    display_name: str
    source: str
    is_active: bool
    created_at: datetime
    secret_count: int = 0

class SecretGenerateIn(BaseModel):
    expires_in_days: int | None = 90

class SecretGenerateOut(BaseModel):
    id: str
    sp_id: str
    secret_prefix: str
    client_secret: str
    expires_at: datetime | None
    created_at: datetime

class SecretMetadataOut(BaseModel):
    id: str
    sp_id: str
    secret_prefix: str
    expires_at: datetime | None
    created_at: datetime

class ServicePrincipalACLAdd(BaseModel):
    principal_id: str
    principal_type: str = "user"  # 'user' | 'group'
    acl_role: str = "manager"      # 'manager' | 'user'

class ServicePrincipalACLOut(BaseModel):
    id: str
    sp_id: str
    principal_id: str
    principal_type: str
    acl_role: str
    granted_at: datetime

class GroupParentAdd(BaseModel):
    parent_group_id: str

class GroupManagerAdd(BaseModel):
    user_id: str

class GroupManagerOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    assigned_at: datetime

import app.user_manager.http.account.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.user_manager.http.account.application.list_users import list_users as list_users_action
from app.user_manager.http.account.application.create_user import create_user as create_user_action
from app.user_manager.http.account.application.suspend_user import suspend_user as suspend_user_action
from app.user_manager.http.account.application.reactivate_user import reactivate_user as reactivate_user_action
from app.user_manager.http.account.application.deactivate_user import deactivate_user as deactivate_user_action
from app.user_manager.http.account.application.change_account_role import change_account_role as change_account_role_action
from app.user_manager.http.account.application.list_invites import list_invites as list_invites_action
from app.user_manager.http.account.application.create_invite import create_invite as create_invite_action
from app.user_manager.http.account.application.revoke_invite import revoke_invite as revoke_invite_action
from app.user_manager.http.account.application.list_groups import list_groups as list_groups_action
from app.user_manager.http.account.application.create_group import create_group as create_group_action
from app.user_manager.http.account.application.list_group_members import list_group_members as list_group_members_action
from app.user_manager.http.account.application.add_group_member import add_group_member as add_group_member_action
from app.user_manager.http.account.application.remove_group_member import remove_group_member as remove_group_member_action
from app.user_manager.http.account.application.list_workspaces_admin import list_workspaces_admin as list_workspaces_admin_action
from app.user_manager.http.account.application.get_audit_log import get_audit_log as get_audit_log_action
from app.user_manager.http.account.application.list_service_principals import list_service_principals as list_service_principals_action
from app.user_manager.http.account.application.create_service_principal import create_service_principal as create_service_principal_action
from app.user_manager.http.account.application.get_service_principal import get_service_principal as get_service_principal_action
from app.user_manager.http.account.application.update_service_principal import update_service_principal as update_service_principal_action
from app.user_manager.http.account.application.delete_service_principal import delete_service_principal as delete_service_principal_action
from app.user_manager.http.account.application.list_service_principal_secrets import list_service_principal_secrets as list_service_principal_secrets_action
from app.user_manager.http.account.application.generate_service_principal_secret import generate_service_principal_secret as generate_service_principal_secret_action
from app.user_manager.http.account.application.revoke_service_principal_secret import revoke_service_principal_secret as revoke_service_principal_secret_action
from app.user_manager.http.account.application.list_parent_groups import list_parent_groups as list_parent_groups_action
from app.user_manager.http.account.application.add_parent_group import add_parent_group as add_parent_group_action
from app.user_manager.http.account.application.remove_parent_group import remove_parent_group as remove_parent_group_action
from app.user_manager.http.account.application.list_group_managers import list_group_managers as list_group_managers_action
from app.user_manager.http.account.application.add_group_manager import add_group_manager as add_group_manager_action
from app.user_manager.http.account.application.remove_group_manager import remove_group_manager as remove_group_manager_action

router = APIRouter(prefix="/api/um/account", tags=["um-account"])


@router.get("/users", response_model=list[UserListItem])
def list_users(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    return list_users_action(admin=admin, account_db=account_db, system_db=system_db)


@router.post("/users", response_model=UserListItem, status_code=201)
def create_user(
    body: UserCreateIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Directly provision a new user in the account (account_admin only)."""
    return create_user_action(body=body, admin=admin, account_db=account_db, system_db=system_db)


@router.post("/users/{user_id}/suspend", status_code=200)
def suspend_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return suspend_user_action(user_id=user_id, admin=admin, account_db=account_db)


@router.post("/users/{user_id}/reactivate", status_code=200)
def reactivate_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return reactivate_user_action(user_id=user_id, admin=admin, account_db=account_db)


@router.post("/users/{user_id}/deactivate", status_code=200)
def deactivate_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return deactivate_user_action(user_id=user_id, admin=admin, account_db=account_db)


@router.patch("/roles/{target_user_id}", status_code=200)
def change_account_role(
    target_user_id: str,
    body: RolePatch,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return change_account_role_action(target_user_id=target_user_id, body=body, admin=admin, account_db=account_db)


@router.get("/invites", response_model=list[InviteOut])
def list_invites(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_invites_action(admin=admin, account_db=account_db)


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(
    body: InviteIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return create_invite_action(body=body, admin=admin, account_db=account_db)


@router.delete("/invites/{invite_id}", status_code=200)
def revoke_invite(
    invite_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return revoke_invite_action(invite_id=invite_id, admin=admin, account_db=account_db)


@router.get("/groups", response_model=list[GroupOut])
def list_groups(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_groups_action(admin=admin, account_db=account_db)


@router.post("/groups", response_model=GroupOut, status_code=201)
def create_group(
    body: GroupCreate,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return create_group_action(body=body, admin=admin, account_db=account_db)


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberOut])
def list_group_members(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_group_members_action(group_id=group_id, admin=admin, account_db=account_db)


@router.post("/groups/{group_id}/members", status_code=201)
def add_group_member(
    group_id: str,
    body: GroupMemberAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return add_group_member_action(group_id=group_id, body=body, admin=admin, account_db=account_db)


@router.delete("/groups/{group_id}/members/{user_id}", status_code=200)
def remove_group_member(
    group_id: str,
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return remove_group_member_action(group_id=group_id, user_id=user_id, admin=admin, account_db=account_db)


@router.get("/workspaces", response_model=list[WorkspaceAdminOut])
def list_workspaces_admin(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    return list_workspaces_admin_action(admin=admin, account_db=account_db, system_db=system_db)


@router.get("/audit-log", response_model=list[AuditLogItem])
def get_audit_log(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    actor_user_id: str | None = Query(None),
    action: str | None = Query(None),
    workspace_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    return get_audit_log_action(admin=admin, account_db=account_db, actor_user_id=actor_user_id, action=action, workspace_id=workspace_id, limit=limit, offset=offset)


@router.get("/service-principals", response_model=list[ServicePrincipalOut])
def list_service_principals(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_service_principals_action(admin=admin, account_db=account_db)


@router.post("/service-principals", response_model=ServicePrincipalOut, status_code=201)
def create_service_principal(
    body: ServicePrincipalCreate,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return create_service_principal_action(body=body, admin=admin, account_db=account_db)


@router.get("/service-principals/{sp_id}", response_model=ServicePrincipalOut)
def get_service_principal(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return get_service_principal_action(sp_id=sp_id, admin=admin, account_db=account_db)


@router.patch("/service-principals/{sp_id}", response_model=ServicePrincipalOut)
def update_service_principal(
    sp_id: str,
    body: ServicePrincipalPatch,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return update_service_principal_action(sp_id=sp_id, body=body, admin=admin, account_db=account_db)


@router.delete("/service-principals/{sp_id}", status_code=200)
def delete_service_principal(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return delete_service_principal_action(sp_id=sp_id, admin=admin, account_db=account_db)


@router.get("/service-principals/{sp_id}/secrets", response_model=list[SecretMetadataOut])
def list_service_principal_secrets(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_service_principal_secrets_action(sp_id=sp_id, admin=admin, account_db=account_db)


@router.post("/service-principals/{sp_id}/secrets", response_model=SecretGenerateOut, status_code=201)
def generate_service_principal_secret(
    sp_id: str,
    body: SecretGenerateIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return generate_service_principal_secret_action(sp_id=sp_id, body=body, admin=admin, account_db=account_db)


@router.delete("/service-principals/{sp_id}/secrets/{secret_id}", status_code=200)
def revoke_service_principal_secret(
    sp_id: str,
    secret_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return revoke_service_principal_secret_action(sp_id=sp_id, secret_id=secret_id, admin=admin, account_db=account_db)


@router.get("/groups/{group_id}/parent-groups", response_model=list[GroupOut])
def list_parent_groups(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_parent_groups_action(group_id=group_id, admin=admin, account_db=account_db)


@router.post("/groups/{group_id}/parent-groups", status_code=201)
def add_parent_group(
    group_id: str,
    body: GroupParentAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return add_parent_group_action(group_id=group_id, body=body, admin=admin, account_db=account_db)


@router.delete("/groups/{group_id}/parent-groups/{parent_group_id}", status_code=200)
def remove_parent_group(
    group_id: str,
    parent_group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return remove_parent_group_action(group_id=group_id, parent_group_id=parent_group_id, admin=admin, account_db=account_db)


@router.get("/groups/{group_id}/managers", response_model=list[GroupManagerOut])
def list_group_managers(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return list_group_managers_action(group_id=group_id, admin=admin, account_db=account_db)


@router.post("/groups/{group_id}/managers", status_code=201)
def add_group_manager(
    group_id: str,
    body: GroupManagerAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return add_group_manager_action(group_id=group_id, body=body, admin=admin, account_db=account_db)


@router.delete("/groups/{group_id}/managers/{user_id}", status_code=200)
def remove_group_manager(
    group_id: str,
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    return remove_group_manager_action(group_id=group_id, user_id=user_id, admin=admin, account_db=account_db)
