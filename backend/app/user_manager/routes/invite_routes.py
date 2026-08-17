"""User Manager — invite acceptance routes (§5.4, §7.4).

GET  /api/um/invites/{token}        → invite details (public, no auth)
POST /api/um/invites/{token}/accept → creates/activates user, writes workspace membership
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_account_db, get_system_db
from app.user_manager.audit import log_action
from app.user_manager.auth_utils import (
    hash_password, hash_refresh_token,
    create_access_token, generate_refresh_token,
)
from app.user_manager.models.account_models import (
    UmUser, UmInvite, UmRefreshToken, UmAccountRoleAssignment,
)
from app.user_manager.models.system_models import UmWorkspaceRoleAssignment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/um/invites", tags=["um-invites"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class InviteDetailsOut(BaseModel):
    id: str
    email: str
    target_scope: str
    target_workspace_id: str | None
    proposed_account_role_id: str | None
    proposed_workspace_role_id: str | None
    status: str
    expires_at: datetime


class AcceptIn(BaseModel):
    password: str
    display_name: str
    confirm_password: str


class AcceptOut(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    account_id: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{token}", response_model=InviteDetailsOut)
def get_invite(token: str, account_db: Session = Depends(get_account_db)):
    invite = _find_valid_invite(token, account_db)
    return InviteDetailsOut(
        id=invite.id,
        email=invite.email,
        target_scope=invite.target_scope,
        target_workspace_id=invite.target_workspace_id,
        proposed_account_role_id=invite.proposed_account_role_id,
        proposed_workspace_role_id=invite.proposed_workspace_role_id,
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post("/{token}/accept", response_model=AcceptOut)
def accept_invite(
    token: str,
    body: AcceptIn,
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    invite = _find_valid_invite(token, account_db)

    # Create or activate user
    user = account_db.query(UmUser).filter(
        UmUser.email == invite.email,
        UmUser.account_id == invite.account_id,
    ).first()
    if user is None:
        user = UmUser(
            account_id=invite.account_id,
            email=invite.email,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
            auth_provider="local",
            status="active",
        )
        account_db.add(user)
        account_db.flush()
    else:
        user.display_name = body.display_name
        user.password_hash = hash_password(body.password)
        user.status = "active"

    # Assign proposed account role if any
    if invite.proposed_account_role_id:
        existing_ara = account_db.query(UmAccountRoleAssignment).filter(
            UmAccountRoleAssignment.account_id == invite.account_id,
            UmAccountRoleAssignment.principal_id == user.id,
            UmAccountRoleAssignment.principal_type == "user",
        ).first()
        if not existing_ara:
            account_db.add(UmAccountRoleAssignment(
                account_id=invite.account_id,
                principal_id=user.id,
                principal_type="user",
                role_id=invite.proposed_account_role_id,
                granted_by=invite.invited_by,
            ))

    # Assign workspace membership if workspace-scoped
    if invite.target_scope == "workspace" and invite.target_workspace_id and invite.proposed_workspace_role_id:
        existing_wra = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.workspace_id == invite.target_workspace_id,
            UmWorkspaceRoleAssignment.principal_id == user.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        ).first()
        if not existing_wra:
            system_db.add(UmWorkspaceRoleAssignment(
                workspace_id=invite.target_workspace_id,
                principal_id=user.id,
                principal_type="user",
                role_id=invite.proposed_workspace_role_id,
                granted_by=invite.invited_by,
            ))

    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)

    log_action(account_db, invite.account_id, "invite_accepted", "user",
               target_id=user.id, metadata={"invite_id": invite.id})

    # Issue tokens
    account_roles = [invite.proposed_account_role_id] if invite.proposed_account_role_id else []
    access = create_access_token(user.id, invite.account_id, account_roles)
    raw_refresh = generate_refresh_token()
    account_db.add(UmRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
    ))

    account_db.commit()
    system_db.commit()

    return AcceptOut(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        account_id=invite.account_id,
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _find_valid_invite(raw_token: str, account_db: Session) -> UmInvite:
    token_hash = hash_refresh_token(raw_token)
    invite = account_db.query(UmInvite).filter(UmInvite.token_hash == token_hash).first()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status == "revoked":
        raise HTTPException(status_code=410, detail="This invite has been revoked. Contact your account admin.")
    if invite.status == "accepted":
        raise HTTPException(status_code=410, detail="This invite has already been accepted.")
    if invite.expires_at < datetime.now(timezone.utc):
        invite.status = "expired"
        account_db.commit()
        raise HTTPException(status_code=410, detail="This invite has expired. Contact your account admin.")
    return invite
