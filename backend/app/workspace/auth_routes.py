"""Auth routes: /me, /workspaces."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.workspace.auth import get_current_principal
from app.workspace.models import Principal, Workspace, WorkspaceMembership
from app.workspace.schemas import PrincipalOut, WorkspaceSlim

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=PrincipalOut)
def me(principal: Principal = Depends(get_current_principal)):
    return principal


@router.get("/workspaces", response_model=list[WorkspaceSlim])
def my_workspaces(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_account_db),
):
    if principal.is_account_admin:
        workspaces = db.query(Workspace).filter(Workspace.status == "active").all()
        return [
            WorkspaceSlim(
                id=w.id, name=w.name, slug=w.slug, status=w.status,
                url=f"/w/{w.slug}", role="admin"
            )
            for w in workspaces
        ]

    memberships = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.principal_id == principal.id)
        .all()
    )
    result = []
    for m in memberships:
        w = db.query(Workspace).filter(Workspace.id == m.workspace_id, Workspace.status == "active").first()
        if w:
            result.append(WorkspaceSlim(
                id=w.id, name=w.name, slug=w.slug, status=w.status,
                url=f"/w/{w.slug}", role=m.role,
            ))
    return result
