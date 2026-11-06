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
