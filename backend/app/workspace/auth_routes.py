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

import app.workspace.http.auth.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.workspace.http.auth.application.me import me as me_action
from app.workspace.http.auth.application.my_workspaces import my_workspaces as my_workspaces_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=PrincipalOut)
def me(principal: Principal = Depends(get_current_principal)):
    return me_action(principal=principal)


@router.get("/workspaces", response_model=list[WorkspaceSlim])
def my_workspaces(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_account_db),
):
    return my_workspaces_action(principal=principal, db=db)
