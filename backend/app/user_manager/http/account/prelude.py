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
