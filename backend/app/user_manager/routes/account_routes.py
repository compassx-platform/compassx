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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/um/account", tags=["um-account"])


# ── Schemas ───────────────────────────────────────────────────────────────────

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


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserListItem])
def list_users(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    users = account_db.query(UmUser).filter(UmUser.account_id == admin.account_id).all()
    result = []
    for u in users:
        ws_count = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.principal_id == u.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        ).count()
        role = get_effective_account_role(u.id, u.account_id, account_db)
        result.append(UserListItem(
            id=u.id, email=u.email, display_name=u.display_name,
            status=u.status, account_role=role, workspace_count=ws_count,
            last_login_at=u.last_login_at, created_at=u.created_at,
        ))
    return result


@router.post("/users", response_model=UserListItem, status_code=201)
def create_user(
    body: UserCreateIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Directly provision a new user in the account (account_admin only)."""
    email = body.email.lower().strip()
    existing = account_db.query(UmUser).filter(
        UmUser.email == email, UmUser.account_id == admin.account_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = UmUser(
        account_id=admin.account_id,
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        auth_provider="local",
        status="active",
    )
    account_db.add(user)
    account_db.flush()

    # Assign requested account role
    from app.user_manager.models.account_models import UmAccountRole
    role_id = body.account_role if account_db.get(UmAccountRole, body.account_role) else "account_viewer"
    account_db.add(UmAccountRoleAssignment(
        account_id=admin.account_id,
        principal_id=user.id,
        principal_type="user",
        role_id=role_id,
        granted_by=admin.id,
    ))

    log_action(
        account_db, admin.account_id, "user_created", "user",
        actor_user_id=admin.id, target_id=user.id,
        metadata={"email": email, "account_role": role_id},
    )
    account_db.commit()
    account_db.refresh(user)

    return UserListItem(
        id=user.id, email=user.email, display_name=user.display_name,
        status=user.status, account_role=role_id, workspace_count=0,
        last_login_at=user.last_login_at, created_at=user.created_at,
    )


@router.post("/users/{user_id}/suspend", status_code=200)
def suspend_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    user = account_db.query(UmUser).filter(
        UmUser.id == user_id, UmUser.account_id == admin.account_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot suspend yourself")
    user.status = "suspended"
    # Delete all refresh tokens (hard revocation per §3)
    account_db.query(UmRefreshToken).filter(UmRefreshToken.user_id == user_id).delete()
    log_action(account_db, admin.account_id, "user_suspended", "user",
               actor_user_id=admin.id, target_id=user_id)
    account_db.commit()
    return {"status": "suspended", "user_id": user_id}


@router.post("/users/{user_id}/reactivate", status_code=200)
def reactivate_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    user = account_db.query(UmUser).filter(
        UmUser.id == user_id, UmUser.account_id == admin.account_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status == "deactivated":
        raise HTTPException(status_code=400, detail="Cannot reactivate a deactivated user")
    user.status = "active"
    log_action(account_db, admin.account_id, "user_reactivated", "user",
               actor_user_id=admin.id, target_id=user_id)
    account_db.commit()
    return {"status": "active", "user_id": user_id}


@router.post("/users/{user_id}/deactivate", status_code=200)
def deactivate_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    user = account_db.query(UmUser).filter(
        UmUser.id == user_id, UmUser.account_id == admin.account_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.status = "deactivated"
    account_db.query(UmRefreshToken).filter(UmRefreshToken.user_id == user_id).delete()
    log_action(account_db, admin.account_id, "user_deactivated", "user",
               actor_user_id=admin.id, target_id=user_id)
    account_db.commit()
    return {"status": "deactivated", "user_id": user_id}


# ── Account role management ───────────────────────────────────────────────────

@router.patch("/roles/{target_user_id}", status_code=200)
def change_account_role(
    target_user_id: str,
    body: RolePatch,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.models.account_models import UmAccountRole
    if not account_db.get(UmAccountRole, body.role_id):
        raise HTTPException(status_code=400, detail=f"Unknown account role: {body.role_id}")

    existing = account_db.query(UmAccountRoleAssignment).filter(
        UmAccountRoleAssignment.account_id == admin.account_id,
        UmAccountRoleAssignment.principal_id == target_user_id,
        UmAccountRoleAssignment.principal_type == "user",
    ).first()
    if existing:
        existing.role_id = body.role_id
        existing.granted_by = admin.id
    else:
        account_db.add(UmAccountRoleAssignment(
            account_id=admin.account_id,
            principal_id=target_user_id,
            principal_type="user",
            role_id=body.role_id,
            granted_by=admin.id,
        ))
    log_action(account_db, admin.account_id, "role_granted", "user",
               actor_user_id=admin.id, target_id=target_user_id,
               metadata={"role_id": body.role_id})
    invalidate_entry_point_cache(target_user_id)
    account_db.commit()
    return {"target_user_id": target_user_id, "role_id": body.role_id}


# ── Invites ───────────────────────────────────────────────────────────────────

@router.get("/invites", response_model=list[InviteOut])
def list_invites(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    rows = account_db.query(UmInvite).filter(
        UmInvite.account_id == admin.account_id,
        UmInvite.status == "pending",
    ).all()
    base = str(__import__("os").environ.get("FRONTEND_ORIGIN", "http://localhost:5173"))
    return [_invite_to_out(r, base) for r in rows]


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(
    body: InviteIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    if body.target_scope not in ("account", "workspace"):
        raise HTTPException(status_code=400, detail="target_scope must be 'account' or 'workspace'")
    if body.target_scope == "workspace" and not body.target_workspace_id:
        raise HTTPException(status_code=400, detail="target_workspace_id required for workspace scope")

    email = body.email.lower().strip()
    # Check if user already exists
    existing_user = account_db.query(UmUser).filter(
        UmUser.email == email, UmUser.account_id == admin.account_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in this account")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_refresh_token(raw_token)  # SHA-256 same as refresh tokens

    invite = UmInvite(
        account_id=admin.account_id,
        email=email,
        token_hash=token_hash,
        target_scope=body.target_scope,
        target_workspace_id=body.target_workspace_id,
        proposed_account_role_id=body.proposed_account_role_id,
        proposed_workspace_role_id=body.proposed_workspace_role_id,
        invited_by=admin.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    account_db.add(invite)
    log_action(account_db, admin.account_id, "invite_created", "invite",
               actor_user_id=admin.id,
               metadata={"email": email, "target_scope": body.target_scope})
    account_db.commit()
    account_db.refresh(invite)

    frontend_origin = __import__("os").environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
    invite_url = f"{frontend_origin}/invite/{raw_token}"
    logger.info("INVITE URL (stub email): %s", invite_url)  # stub — log instead of email

    return _invite_to_out(invite, frontend_origin, raw_token)


@router.delete("/invites/{invite_id}", status_code=200)
def revoke_invite(
    invite_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    invite = account_db.query(UmInvite).filter(
        UmInvite.id == invite_id, UmInvite.account_id == admin.account_id
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.status = "revoked"
    log_action(account_db, admin.account_id, "invite_revoked", "invite",
               actor_user_id=admin.id, target_id=invite_id)
    account_db.commit()
    return {"status": "revoked", "invite_id": invite_id}


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


# ── Groups ────────────────────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str


@router.get("/groups", response_model=list[GroupOut])
def list_groups(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    groups = account_db.query(UmGroup).filter(UmGroup.account_id == admin.account_id).all()
    return [GroupOut(
        id=g.id, name=g.name, source=g.source,
        member_count=len(g.members), created_at=g.created_at,
    ) for g in groups]


@router.post("/groups", response_model=GroupOut, status_code=201)
def create_group(
    body: GroupCreate,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    existing = account_db.query(UmGroup).filter(
        UmGroup.account_id == admin.account_id, UmGroup.name == body.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group name already exists")
    g = UmGroup(account_id=admin.account_id, name=body.name)
    account_db.add(g)
    account_db.commit()
    account_db.refresh(g)
    return GroupOut(id=g.id, name=g.name, source=g.source, member_count=0, created_at=g.created_at)


@router.get("/groups/{group_id}/members", response_model=list[GroupMemberOut])
def list_group_members(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    g = assert_group_exists(group_id, admin.account_id, account_db)
    result = []
    for gm in g.members:
        u = account_db.query(UmUser).filter(UmUser.id == gm.user_id).first()
        if u:
            result.append(GroupMemberOut(
                user_id=u.id, email=u.email, display_name=u.display_name, added_at=gm.added_at
            ))
    return result


class GroupMemberAdd(BaseModel):
    user_id: str


@router.post("/groups/{group_id}/members", status_code=201)
def add_group_member(
    group_id: str,
    body: GroupMemberAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)
    user = account_db.query(UmUser).filter(
        UmUser.id == body.user_id, UmUser.account_id == admin.account_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = account_db.query(UmGroupMember).filter(
        UmGroupMember.group_id == group_id, UmGroupMember.user_id == body.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already in group")
    account_db.add(UmGroupMember(group_id=group_id, user_id=body.user_id))
    invalidate_entry_point_cache(body.user_id)
    account_db.commit()
    return {"group_id": group_id, "user_id": body.user_id}


@router.delete("/groups/{group_id}/members/{user_id}", status_code=200)
def remove_group_member(
    group_id: str,
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)
    gm = account_db.query(UmGroupMember).filter(
        UmGroupMember.group_id == group_id, UmGroupMember.user_id == user_id
    ).first()
    if not gm:
        raise HTTPException(status_code=404, detail="Member not found")
    account_db.delete(gm)
    invalidate_entry_point_cache(user_id)
    account_db.commit()
    return {"group_id": group_id, "user_id": user_id, "status": "removed"}


# ── Workspaces admin view ─────────────────────────────────────────────────────

class WorkspaceAdminOut(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    member_count: int
    created_at: datetime


@router.get("/workspaces", response_model=list[WorkspaceAdminOut])
def list_workspaces_admin(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    from app.workspace.models import Workspace as LegacyWs
    workspaces = account_db.query(LegacyWs).filter(LegacyWs.account_id == admin.account_id).all()
    result = []
    for ws in workspaces:
        member_count = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.workspace_id == ws.id
        ).count()
        result.append(WorkspaceAdminOut(
            id=ws.id, name=ws.name, slug=ws.slug,
            status=ws.status, member_count=member_count,
            created_at=ws.created_at,
        ))
    return result


# ── Audit log ─────────────────────────────────────────────────────────────────

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
    q = account_db.query(UmAuditLog).filter(UmAuditLog.account_id == admin.account_id)
    if actor_user_id:
        q = q.filter(UmAuditLog.actor_user_id == actor_user_id)
    if action:
        q = q.filter(UmAuditLog.action == action)
    if workspace_id:
        q = q.filter(UmAuditLog.workspace_id == workspace_id)
    rows = q.order_by(UmAuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [AuditLogItem(
        id=r.id, actor_user_id=r.actor_user_id, action=r.action,
        target_type=r.target_type, target_id=r.target_id,
        workspace_id=r.workspace_id, metadata=r.metadata_,
        created_at=r.created_at,
    ) for r in rows]


# ── Service Principals ────────────────────────────────────────────────────────

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


@router.get("/service-principals", response_model=list[ServicePrincipalOut])
def list_service_principals(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sps = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.account_id == admin.account_id
    ).all()
    return [
        ServicePrincipalOut(
            id=sp.id,
            account_id=sp.account_id,
            application_id=sp.application_id,
            display_name=sp.display_name,
            source=sp.source,
            is_active=sp.is_active,
            created_at=sp.created_at,
            secret_count=len(sp.secrets),
        )
        for sp in sps
    ]


@router.post("/service-principals", response_model=ServicePrincipalOut, status_code=201)
def create_service_principal(
    body: ServicePrincipalCreate,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    name = body.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="display_name cannot be empty")
    sp = UmServicePrincipal(
        account_id=admin.account_id,
        display_name=name,
    )
    account_db.add(sp)
    log_action(account_db, admin.account_id, "service_principal_created", "service_principal",
               actor_user_id=admin.id, metadata={"display_name": name, "application_id": sp.application_id})
    account_db.commit()
    account_db.refresh(sp)
    return ServicePrincipalOut(
        id=sp.id,
        account_id=sp.account_id,
        application_id=sp.application_id,
        display_name=sp.display_name,
        source=sp.source,
        is_active=sp.is_active,
        created_at=sp.created_at,
        secret_count=0,
    )


@router.get("/service-principals/{sp_id}", response_model=ServicePrincipalOut)
def get_service_principal(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")
    return ServicePrincipalOut(
        id=sp.id,
        account_id=sp.account_id,
        application_id=sp.application_id,
        display_name=sp.display_name,
        source=sp.source,
        is_active=sp.is_active,
        created_at=sp.created_at,
        secret_count=len(sp.secrets),
    )


@router.patch("/service-principals/{sp_id}", response_model=ServicePrincipalOut)
def update_service_principal(
    sp_id: str,
    body: ServicePrincipalPatch,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")
    if body.display_name is not None:
        sp.display_name = body.display_name.strip()
    if body.is_active is not None:
        sp.is_active = body.is_active
    log_action(account_db, admin.account_id, "service_principal_updated", "service_principal",
               actor_user_id=admin.id, target_id=sp.id,
               metadata={"display_name": sp.display_name, "is_active": sp.is_active})
    account_db.commit()
    account_db.refresh(sp)
    return ServicePrincipalOut(
        id=sp.id,
        account_id=sp.account_id,
        application_id=sp.application_id,
        display_name=sp.display_name,
        source=sp.source,
        is_active=sp.is_active,
        created_at=sp.created_at,
        secret_count=len(sp.secrets),
    )


@router.delete("/service-principals/{sp_id}", status_code=200)
def delete_service_principal(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")
    account_db.delete(sp)
    log_action(account_db, admin.account_id, "service_principal_deleted", "service_principal",
               actor_user_id=admin.id, target_id=sp_id)
    account_db.commit()
    return {"status": "deleted", "sp_id": sp_id}


# ── Service Principal Secrets ─────────────────────────────────────────────────

@router.get("/service-principals/{sp_id}/secrets", response_model=list[SecretMetadataOut])
def list_service_principal_secrets(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")
    secrets_list = account_db.query(UmServicePrincipalSecret).filter(
        UmServicePrincipalSecret.sp_id == sp_id
    ).all()
    return [
        SecretMetadataOut(
            id=s.id,
            sp_id=s.sp_id,
            secret_prefix=s.secret_prefix,
            expires_at=s.expires_at,
            created_at=s.created_at,
        )
        for s in secrets_list
    ]


@router.post("/service-principals/{sp_id}/secrets", response_model=SecretGenerateOut, status_code=201)
def generate_service_principal_secret(
    sp_id: str,
    body: SecretGenerateIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")

    raw_token = f"cpx_sp_{secrets.token_urlsafe(32)}"
    prefix = f"{raw_token[:12]}..."
    secret_hash = hash_password(raw_token)
    expires_at = None
    if body.expires_in_days and body.expires_in_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    sec = UmServicePrincipalSecret(
        sp_id=sp.id,
        secret_hash=secret_hash,
        secret_prefix=prefix,
        expires_at=expires_at,
    )
    account_db.add(sec)
    log_action(account_db, admin.account_id, "sp_secret_generated", "service_principal",
               actor_user_id=admin.id, target_id=sp.id, metadata={"secret_prefix": prefix})
    account_db.commit()
    account_db.refresh(sec)

    return SecretGenerateOut(
        id=sec.id,
        sp_id=sec.sp_id,
        secret_prefix=sec.secret_prefix,
        client_secret=raw_token,
        expires_at=sec.expires_at,
        created_at=sec.created_at,
    )


@router.delete("/service-principals/{sp_id}/secrets/{secret_id}", status_code=200)
def revoke_service_principal_secret(
    sp_id: str,
    secret_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")

    sec = account_db.query(UmServicePrincipalSecret).filter(
        UmServicePrincipalSecret.id == secret_id,
        UmServicePrincipalSecret.sp_id == sp_id,
    ).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Secret not found")

    account_db.delete(sec)
    log_action(account_db, admin.account_id, "sp_secret_revoked", "service_principal",
               actor_user_id=admin.id, target_id=sp.id, metadata={"secret_id": secret_id})
    account_db.commit()
    return {"status": "revoked", "secret_id": secret_id}


# ── Nested Groups (Parent / Child Groups) ────────────────────────────────────

class GroupParentAdd(BaseModel):
    parent_group_id: str


@router.get("/groups/{group_id}/parent-groups", response_model=list[GroupOut])
def list_parent_groups(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    nestings = account_db.query(UmGroupNesting).filter(
        UmGroupNesting.child_group_id == group_id
    ).all()
    parent_ids = [n.parent_group_id for n in nestings]
    if not parent_ids:
        return []

    parents = account_db.query(UmGroup).filter(
        UmGroup.id.in_(parent_ids),
        UmGroup.account_id == admin.account_id,
    ).all()
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            source=g.source,
            member_count=len(g.members),
            created_at=g.created_at,
        )
        for g in parents
    ]


@router.post("/groups/{group_id}/parent-groups", status_code=201)
def add_parent_group(
    group_id: str,
    body: GroupParentAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    from sqlalchemy import text

    assert_group_exists(group_id, admin.account_id, account_db)
    assert_group_exists(body.parent_group_id, admin.account_id, account_db)

    if group_id == body.parent_group_id:
        raise HTTPException(status_code=400, detail="A group cannot be a parent of itself")

    # Cycle detection: check if group_id is already an ancestor of parent_group_id
    cycle_check_query = text("""
        WITH RECURSIVE ancestors AS (
            SELECT parent_group_id FROM um_group_nestings WHERE child_group_id = :parent_id
            UNION
            SELECT gn.parent_group_id
            FROM um_group_nestings gn
            JOIN ancestors a ON gn.child_group_id = a.parent_group_id
        )
        SELECT 1 FROM ancestors WHERE parent_group_id = :child_id LIMIT 1;
    """)
    has_cycle = account_db.execute(cycle_check_query, {
        "parent_id": body.parent_group_id,
        "child_id": group_id,
    }).first()
    if has_cycle:
        raise HTTPException(status_code=400, detail="Circular group nesting detected")

    existing = account_db.query(UmGroupNesting).filter(
        UmGroupNesting.parent_group_id == body.parent_group_id,
        UmGroupNesting.child_group_id == group_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group is already nested under this parent")

    nesting = UmGroupNesting(
        parent_group_id=body.parent_group_id,
        child_group_id=group_id,
    )
    account_db.add(nesting)
    log_action(account_db, admin.account_id, "group_nested", "group",
               actor_user_id=admin.id, target_id=group_id,
               metadata={"parent_group_id": body.parent_group_id})
    account_db.commit()
    return {"child_group_id": group_id, "parent_group_id": body.parent_group_id}


@router.delete("/groups/{group_id}/parent-groups/{parent_group_id}", status_code=200)
def remove_parent_group(
    group_id: str,
    parent_group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    nesting = account_db.query(UmGroupNesting).filter(
        UmGroupNesting.parent_group_id == parent_group_id,
        UmGroupNesting.child_group_id == group_id,
    ).first()
    if not nesting:
        raise HTTPException(status_code=404, detail="Parent group relationship not found")

    account_db.delete(nesting)
    log_action(account_db, admin.account_id, "group_unnested", "group",
               actor_user_id=admin.id, target_id=group_id,
               metadata={"parent_group_id": parent_group_id})
    account_db.commit()
    return {"child_group_id": group_id, "parent_group_id": parent_group_id, "status": "removed"}


# ── Group Managers (Delegated Administration) ────────────────────────────────

class GroupManagerAdd(BaseModel):
    user_id: str


class GroupManagerOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    assigned_at: datetime


@router.get("/groups/{group_id}/managers", response_model=list[GroupManagerOut])
def list_group_managers(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    g = assert_group_exists(group_id, admin.account_id, account_db)
    result = []
    for m in g.managers:
        u = account_db.query(UmUser).filter(UmUser.id == m.user_id).first()
        if u:
            result.append(GroupManagerOut(
                user_id=u.id,
                email=u.email,
                display_name=u.display_name,
                assigned_at=m.assigned_at,
            ))
    return result


@router.post("/groups/{group_id}/managers", status_code=201)
def add_group_manager(
    group_id: str,
    body: GroupManagerAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    user = account_db.query(UmUser).filter(
        UmUser.id == body.user_id,
        UmUser.account_id == admin.account_id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = account_db.query(UmGroupManager).filter(
        UmGroupManager.group_id == group_id,
        UmGroupManager.user_id == body.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a manager of this group")

    mgr = UmGroupManager(group_id=group_id, user_id=body.user_id)
    account_db.add(mgr)
    log_action(account_db, admin.account_id, "group_manager_added", "group",
               actor_user_id=admin.id, target_id=group_id, metadata={"user_id": body.user_id})
    account_db.commit()
    return {"group_id": group_id, "user_id": body.user_id}


@router.delete("/groups/{group_id}/managers/{user_id}", status_code=200)
def remove_group_manager(
    group_id: str,
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    mgr = account_db.query(UmGroupManager).filter(
        UmGroupManager.group_id == group_id,
        UmGroupManager.user_id == user_id,
    ).first()
    if not mgr:
        raise HTTPException(status_code=404, detail="Group manager not found")

    account_db.delete(mgr)
    log_action(account_db, admin.account_id, "group_manager_removed", "group",
               actor_user_id=admin.id, target_id=group_id, metadata={"user_id": user_id})
    account_db.commit()
    return {"group_id": group_id, "user_id": user_id, "status": "removed"}

