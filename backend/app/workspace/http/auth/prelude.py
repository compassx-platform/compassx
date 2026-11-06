"""Auth routes: /me, /workspaces."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.database import get_account_db

from app.workspace.auth import get_current_principal

from app.workspace.models import Principal, Workspace, WorkspaceMembership

from app.workspace.schemas import PrincipalOut, WorkspaceSlim

logger = logging.getLogger("app.workspace.auth_routes")

router = APIRouter(prefix="/api/auth", tags=["auth"])
