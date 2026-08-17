"""User Manager — auth routes (§5.2).

POST /api/um/auth/login    { email, password } → { access_token, refresh_token, user }
POST /api/um/auth/refresh  { refresh_token }   → { access_token }
POST /api/um/auth/logout   revokes refresh token
GET  /api/um/auth/me       → current user info + effective account role
GET  /api/um/auth/workspaces → user's workspace memberships
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_account_db, get_system_db
from app.user_manager.auth_utils import (
    verify_password, create_access_token,
    generate_refresh_token, hash_refresh_token,
)
from app.user_manager.dependencies import get_current_um_user, get_effective_account_role
from app.user_manager.models.account_models import UmUser, UmRefreshToken, UmAccountRoleAssignment
from app.user_manager.models.system_models import UmWorkspaceRoleAssignment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/um/auth", tags=["um-auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    display_name: str | None
    account_id: str
    is_account_admin: bool


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    account_id: str
    status: str
    account_role: str | None
    last_login_at: datetime | None
    created_at: datetime


class WorkspaceMembershipOut(BaseModel):
    workspace_id: str
    workspace_name: str | None
    workspace_slug: str | None = None
    role_id: str
    is_default: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _issue_tokens(user: UmUser, account_db: Session) -> tuple[str, str]:
    """Issue access + refresh tokens, persist refresh token hash."""
    account_roles = [
        row.role_id
        for row in account_db.query(UmAccountRoleAssignment)
        .filter(
            UmAccountRoleAssignment.principal_id == user.id,
            UmAccountRoleAssignment.principal_type == "user",
        )
        .all()
    ]
    access = create_access_token(user.id, user.account_id, account_roles)
    raw_refresh = generate_refresh_token()
    account_db.add(UmRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
    ))
    return access, raw_refresh


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, account_db: Session = Depends(get_account_db)):
    user = (
        account_db.query(UmUser)
        .filter(UmUser.email == body.email.lower().strip())
        .first()
    )
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.status == "suspended":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")
    if user.status == "deactivated":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    if user.status == "invited":
        # Allow login after invitation — they set their password during acceptance
        user.status = "active"

    user.last_login_at = datetime.now(timezone.utc)
    access, raw_refresh = _issue_tokens(user, account_db)
    account_db.commit()

    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    return LoginOut(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        account_id=user.account_id,
        is_account_admin=(account_role == "account_admin"),
    )


@router.post("/refresh", response_model=TokenOut)
def refresh_token(body: RefreshIn, account_db: Session = Depends(get_account_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    row = (
        account_db.query(UmRefreshToken)
        .filter(
            UmRefreshToken.token_hash == token_hash,
            UmRefreshToken.revoked_at == None,
            UmRefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = account_db.query(UmUser).filter(UmUser.id == row.user_id).first()
    if user is None or user.status in ("suspended", "deactivated"):
        row.revoked_at = datetime.now(timezone.utc)
        account_db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not active")

    account_roles = [
        r.role_id
        for r in account_db.query(UmAccountRoleAssignment)
        .filter(
            UmAccountRoleAssignment.principal_id == user.id,
            UmAccountRoleAssignment.principal_type == "user",
        )
        .all()
    ]
    access = create_access_token(user.id, user.account_id, account_roles)
    account_db.commit()
    return TokenOut(access_token=access)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, account_db: Session = Depends(get_account_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    row = account_db.query(UmRefreshToken).filter(UmRefreshToken.token_hash == token_hash).first()
    if row:
        row.revoked_at = datetime.now(timezone.utc)
        account_db.commit()


@router.get("/me", response_model=UserOut)
def me(
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
):
    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        account_id=user.account_id,
        status=user.status,
        account_role=account_role,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get("/workspaces", response_model=list[WorkspaceMembershipOut])
def my_workspaces(
    user: UmUser = Depends(get_current_um_user),
    system_db: Session = Depends(get_system_db),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.models.account_models import UmGroupMember
    from app.workspace.models import Workspace as LegacyWs

    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    is_admin = (account_role == "account_admin")

    # Direct assignments
    direct = (
        system_db.query(UmWorkspaceRoleAssignment)
        .filter(
            UmWorkspaceRoleAssignment.principal_id == user.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        )
        .all()
    )
    group_ids = [gm.group_id for gm in account_db.query(UmGroupMember).filter(UmGroupMember.user_id == user.id).all()]
    group_rows = []
    if group_ids:
        group_rows = (
            system_db.query(UmWorkspaceRoleAssignment)
            .filter(
                UmWorkspaceRoleAssignment.principal_id.in_(group_ids),
                UmWorkspaceRoleAssignment.principal_type == "group",
            )
            .all()
        )

    result = []
    seen = set()
    for row in direct + group_rows:
        if row.workspace_id in seen:
            continue
        seen.add(row.workspace_id)
        is_uuid = False
        try:
            from uuid import UUID
            UUID(str(row.workspace_id))
            is_uuid = True
        except (ValueError, TypeError):
            pass

        ws = account_db.query(LegacyWs).filter(
            LegacyWs.id == row.workspace_id if is_uuid else LegacyWs.slug == row.workspace_id
        ).first()
        if ws:
            seen.add(ws.id)
            seen.add(ws.slug)
        result.append(WorkspaceMembershipOut(
            workspace_id=ws.id if ws else row.workspace_id,
            workspace_name=ws.name if ws else None,
            workspace_slug=ws.slug if ws else None,
            role_id=row.role_id,
            is_default=row.is_default,
        ))

    # If user is account_admin, ensure ALL active workspaces in user's account (or system) are included
    if is_admin:
        all_account_workspaces = (
            account_db.query(LegacyWs)
            .filter(
                (LegacyWs.account_id == user.account_id) | (LegacyWs.account_id.is_(None)),
                LegacyWs.status == "active"
            )
            .all()
        )
        if not all_account_workspaces:
            all_account_workspaces = (
                account_db.query(LegacyWs)
                .filter(LegacyWs.status == "active")
                .all()
            )
        for ws in all_account_workspaces:
            if ws.id not in seen and ws.slug not in seen:
                seen.add(ws.id)
                seen.add(ws.slug)
                result.append(WorkspaceMembershipOut(
                    workspace_id=ws.id,
                    workspace_name=ws.name,
                    workspace_slug=ws.slug,
                    role_id="workspace_admin",
                    is_default=(len(result) == 0),
                ))

    return result
