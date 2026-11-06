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

logger = logging.getLogger("app.user_manager.routes.auth_routes")

router = APIRouter(prefix="/api/um/auth", tags=["um-auth"])

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

class ServicePrincipalTokenIn(BaseModel):
    application_id: str
    client_secret: str

class ServicePrincipalTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    sp_id: str
    application_id: str
    display_name: str
    account_id: str

class MyGroupOut(BaseModel):
    id: str
    name: str
    source: str
    member_count: int

import app.user_manager.http.auth.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.user_manager.http.auth.application.login import login as login_action
from app.user_manager.http.auth.application.refresh_token import refresh_token as refresh_token_action
from app.user_manager.http.auth.application.logout import logout as logout_action
from app.user_manager.http.auth.application.me import me as me_action
from app.user_manager.http.auth.application.my_workspaces import my_workspaces as my_workspaces_action
from app.user_manager.http.auth.application.authenticate_service_principal import authenticate_service_principal as authenticate_service_principal_action
from app.user_manager.http.auth.application.get_my_groups import get_my_groups as get_my_groups_action

router = APIRouter(prefix="/api/um/auth", tags=["um-auth"])


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, account_db: Session = Depends(get_account_db)):
    return login_action(body=body, account_db=account_db)


@router.post("/refresh", response_model=TokenOut)
def refresh_token(body: RefreshIn, account_db: Session = Depends(get_account_db)):
    return refresh_token_action(body=body, account_db=account_db)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, account_db: Session = Depends(get_account_db)):
    return logout_action(body=body, account_db=account_db)


@router.get("/me", response_model=UserOut)
def me(
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
):
    return me_action(user=user, account_db=account_db)


@router.get("/workspaces", response_model=list[WorkspaceMembershipOut])
def my_workspaces(
    user: UmUser = Depends(get_current_um_user),
    system_db: Session = Depends(get_system_db),
    account_db: Session = Depends(get_account_db),
):
    return my_workspaces_action(user=user, system_db=system_db, account_db=account_db)


@router.post("/sp-token", response_model=ServicePrincipalTokenOut)
def authenticate_service_principal(
    body: ServicePrincipalTokenIn,
    account_db: Session = Depends(get_account_db),
):
    return authenticate_service_principal_action(body=body, account_db=account_db)


@router.get("/my-groups", response_model=list[MyGroupOut])
def get_my_groups(
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
):
    return get_my_groups_action(user=user, account_db=account_db)
