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
from app.user_manager.models.account_models import UmUser, UmInvite
from app.user_manager.models.system_models import UmWorkspaceRoleAssignment, UmWorkspaceRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/um/workspaces", tags=["um-workspace-members"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class MemberOut(BaseModel):
    assignment_id: str
    user_id: str | None
    group_id: str | None
    principal_type: str
    email: str | None
    display_name: str | None
    role_id: str
    is_default: bool
    granted_at: datetime


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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_ws_admin(workspace_id: str, user: UmUser, account_db: Session, system_db: Session):
    require_workspace_admin(workspace_id, user, account_db, system_db)


def _valid_ws_role(role_id: str, system_db: Session) -> None:
    if not system_db.get(UmWorkspaceRole, role_id):
        raise HTTPException(status_code=400, detail=f"Unknown workspace role: {role_id}")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_workspace_members(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    # Any workspace member (or account admin) can view the list
    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    ws_role = get_effective_workspace_role(user.id, workspace_id, system_db, account_db)
    if account_role != "account_admin" and ws_role is None:
        raise HTTPException(status_code=403, detail="No access to this workspace")

    rows = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id
    ).all()

    result = []
    for row in rows:
        email = display = None
        if row.principal_type == "user":
            u = account_db.query(UmUser).filter(UmUser.id == row.principal_id).first()
            if u:
                email, display = u.email, u.display_name
        result.append(MemberOut(
            assignment_id=row.id,
            user_id=row.principal_id if row.principal_type == "user" else None,
            group_id=row.principal_id if row.principal_type == "group" else None,
            principal_type=row.principal_type,
            email=email, display_name=display,
            role_id=row.role_id, is_default=row.is_default,
            granted_at=row.granted_at,
        ))
    return result


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
    _require_ws_admin(workspace_id, user, account_db, system_db)
    assert_workspace_exists_in_account_db(workspace_id, account_db)
    _valid_ws_role(body.role_id, system_db)

    email_or_id = body.email_or_user_id.strip()
    is_uuid = False
    try:
        from uuid import UUID
        UUID(email_or_id)
        is_uuid = True
    except (ValueError, TypeError):
        pass

    target_user = None
    if is_uuid:
        target_user = account_db.query(UmUser).filter(UmUser.id == email_or_id).first()

    if target_user is None:
        target_user = account_db.query(UmUser).filter(
            UmUser.email == email_or_id.lower(),
            UmUser.account_id == user.account_id,
        ).first()

    if target_user is None:
        # Create invite
        raw_token = secrets.token_urlsafe(32)
        invite = UmInvite(
            account_id=user.account_id,
            email=email_or_id.lower(),
            token_hash=hash_refresh_token(raw_token),
            target_scope="workspace",
            target_workspace_id=workspace_id,
            proposed_workspace_role_id=body.role_id,
            invited_by=user.id,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        account_db.add(invite)
        log_action(account_db, user.account_id, "invite_created", "invite",
                   actor_user_id=user.id, workspace_id=workspace_id,
                   metadata={"email": email_or_id, "role_id": body.role_id})
        account_db.commit()
        frontend_origin = __import__("os").environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
        invite_url = f"{frontend_origin}/invite/{raw_token}"
        logger.info("WORKSPACE INVITE URL (stub): %s", invite_url)
        return {"type": "invited", "invite_id": invite.id, "invite_url": invite_url}

    # Add directly via workspace_role_assignments
    existing = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == target_user.id,
        UmWorkspaceRoleAssignment.principal_type == "user",
    ).first()
    if existing:
        existing.role_id = body.role_id
        existing.granted_by = user.id
    else:
        system_db.add(UmWorkspaceRoleAssignment(
            workspace_id=workspace_id,
            principal_id=target_user.id,
            principal_type="user",
            role_id=body.role_id,
            granted_by=user.id,
        ))
    log_action(account_db, user.account_id, "member_added", "user",
               actor_user_id=user.id, target_id=target_user.id, workspace_id=workspace_id,
               metadata={"role_id": body.role_id})
    system_db.commit()
    account_db.commit()
    invalidate_entry_point_cache(target_user.id)
    return {"type": "added", "user_id": target_user.id}


@router.post("/{workspace_id}/members/create", status_code=201)
def create_workspace_user(
    workspace_id: str,
    body: WorkspaceUserCreateIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Directly provision a new user and add them to the workspace in one step."""
    _require_ws_admin(workspace_id, user, account_db, system_db)
    assert_workspace_exists_in_account_db(workspace_id, account_db)
    _valid_ws_role(body.role_id, system_db)

    email = body.email.lower().strip()
    existing_user = account_db.query(UmUser).filter(
        UmUser.email == email, UmUser.account_id == user.account_id
    ).first()

    if existing_user:
        # User already exists in account_db — grant or update workspace access directly
        ass = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.workspace_id == workspace_id,
            UmWorkspaceRoleAssignment.principal_id == existing_user.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        ).first()
        if ass:
            ass.role_id = body.role_id
            ass.granted_by = user.id
        else:
            system_db.add(UmWorkspaceRoleAssignment(
                workspace_id=workspace_id,
                principal_id=existing_user.id,
                principal_type="user",
                role_id=body.role_id,
                granted_by=user.id,
            ))
        system_db.commit()
        account_db.commit()
        invalidate_entry_point_cache(existing_user.id)
        return {"id": existing_user.id, "email": existing_user.email, "display_name": existing_user.display_name, "status": "added_existing"}

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    from app.user_manager.auth_utils import hash_password
    from app.user_manager.models.account_models import UmAccountRoleAssignment

    new_user = UmUser(
        account_id=user.account_id,
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        auth_provider="local",
        status="active",
    )
    account_db.add(new_user)
    account_db.flush()

    # Assign default account_viewer role in account_db
    account_db.add(UmAccountRoleAssignment(
        account_id=user.account_id,
        principal_id=new_user.id,
        principal_type="user",
        role_id="account_viewer",
        granted_by=user.id,
    ))

    # Assign requested workspace role in system_db
    system_db.add(UmWorkspaceRoleAssignment(
        workspace_id=workspace_id,
        principal_id=new_user.id,
        principal_type="user",
        role_id=body.role_id,
        granted_by=user.id,
    ))

    log_action(account_db, user.account_id, "user_created", "user",
               actor_user_id=user.id, target_id=new_user.id, workspace_id=workspace_id,
               metadata={"email": email, "workspace_role": body.role_id})

    account_db.commit()
    system_db.commit()

    return {"type": "created", "user_id": new_user.id, "email": new_user.email, "role_id": body.role_id}


@router.patch("/{workspace_id}/members/{user_id}/role", status_code=200)
def update_member_role(
    workspace_id: str,
    user_id: str,
    body: RolePatch,
    actor: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    _require_ws_admin(workspace_id, actor, account_db, system_db)
    _valid_ws_role(body.role_id, system_db)

    row = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == user_id,
        UmWorkspaceRoleAssignment.principal_type == "user",
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Membership not found")
    row.role_id = body.role_id
    row.granted_by = actor.id
    log_action(account_db, actor.account_id, "role_changed", "user",
               actor_user_id=actor.id, target_id=user_id, workspace_id=workspace_id,
               metadata={"role_id": body.role_id})
    system_db.commit()
    account_db.commit()
    invalidate_entry_point_cache(user_id)
    return {"user_id": user_id, "workspace_id": workspace_id, "role_id": body.role_id}


@router.delete("/{workspace_id}/members/{user_id}", status_code=200)
def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    actor: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    _require_ws_admin(workspace_id, actor, account_db, system_db)

    row = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == user_id,
        UmWorkspaceRoleAssignment.principal_type == "user",
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Membership not found")
    system_db.delete(row)
    log_action(account_db, actor.account_id, "member_removed", "user",
               actor_user_id=actor.id, target_id=user_id, workspace_id=workspace_id)
    system_db.commit()
    account_db.commit()
    invalidate_entry_point_cache(user_id)
    return {"status": "removed", "user_id": user_id, "workspace_id": workspace_id}


@router.post("/{workspace_id}/set-default", status_code=200)
def set_default_workspace(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    system_db: Session = Depends(get_system_db),
):
    """Set is_default=true for this workspace for the current user (§5.6)."""
    # Clear existing defaults for this user
    system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.principal_id == user.id,
        UmWorkspaceRoleAssignment.principal_type == "user",
        UmWorkspaceRoleAssignment.is_default == True,
    ).update({"is_default": False})

    target = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == user.id,
        UmWorkspaceRoleAssignment.principal_type == "user",
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Not a member of this workspace")
    target.is_default = True
    system_db.commit()
    invalidate_entry_point_cache(user.id)
    return {"workspace_id": workspace_id, "is_default": True}
