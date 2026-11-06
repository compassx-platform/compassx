"""User Manager — /api/um/setup/* routes (§5.1).

GET  /api/um/setup/status   → { needs_setup: bool }
POST /api/um/setup/complete → spans both DBs, returns access+refresh tokens
"""

from __future__ import annotations

import logging

import secrets

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status

from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from app.config import settings

from app.database import get_account_db, get_system_db

from app.user_manager.auth_utils import hash_password, create_access_token, generate_refresh_token, hash_refresh_token

from app.user_manager.models.account_models import (
    UmUser, UmRefreshToken, UmAccountRoleAssignment,
)

from app.user_manager.models.system_models import UmWorkspaceRoleAssignment

from app.user_manager.seed import run_all_seeds

logger = logging.getLogger("app.user_manager.routes.setup_routes")

router = APIRouter(prefix="/api/um/setup", tags=["setup"])

class SetupStatusOut(BaseModel):
    needs_setup: bool

class SetupCompleteIn(BaseModel):
    account_name: str
    admin_email: str
    admin_password: str
    admin_display_name: str
    workspace_name: str | None = None

class SetupCompleteOut(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    account_id: str

import app.user_manager.http.setup.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.user_manager.http.setup.application.setup_status import setup_status as setup_status_action
from app.user_manager.http.setup.application.setup_complete import setup_complete as setup_complete_action

router = APIRouter(prefix="/api/um/setup", tags=["setup"])


@router.get("/status", response_model=SetupStatusOut)
def setup_status(account_db: Session = Depends(get_account_db)):
    """Check whether initial setup has been completed."""
    return setup_status_action(account_db=account_db)


@router.post("/complete", response_model=SetupCompleteOut, status_code=201)
def setup_complete(
    body: SetupCompleteIn,
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
    request: Request = None,
):
    """One-time setup: create account, admin user, first workspace, seed static tables.

    Guards against concurrent double-submit by checking existing users.
    Once a UmUser exists, returns 403 permanently.
    """
    return setup_complete_action(body=body, account_db=account_db, system_db=system_db, request=request)
