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

logger = logging.getLogger("app.user_manager.routes.invite_routes")

router = APIRouter(prefix="/api/um/invites", tags=["um-invites"])

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
