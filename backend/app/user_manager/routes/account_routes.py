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
