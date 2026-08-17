"""User Manager — cross-database existence validation helpers (§1.2).

The spec mandates that any write referencing the other database must perform
an explicit existence check via the service layer (no DB-enforced FK across DBs).
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.user_manager.models.account_models import UmUser, UmGroup
from app.user_manager.models.system_models import UmWorkspaceRoleAssignment


def assert_user_exists(user_id: str, account_db: Session) -> UmUser:
    """Raise 404 if user_id doesn't exist in account_db."""
    user = account_db.query(UmUser).filter(UmUser.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    return user


def assert_workspace_exists_in_account_db(workspace_id: str, account_db: Session):
    """Raise 404 if workspace_id doesn't exist in account_db.workspaces.
    Safely queries UUID or slug depending on input string structure.
    """
    from uuid import UUID
    from app.workspace.models import Workspace

    is_uuid = False
    try:
        UUID(str(workspace_id))
        is_uuid = True
    except (ValueError, TypeError):
        pass

    if is_uuid:
        ws = account_db.query(Workspace).filter(Workspace.id == workspace_id).first()
    else:
        ws = account_db.query(Workspace).filter(Workspace.slug == workspace_id).first()

    if ws is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workspace {workspace_id} not found")
    return ws


def assert_group_exists(group_id: str, account_id: str, account_db: Session) -> UmGroup:
    """Raise 404 if group_id doesn't exist in this account."""
    group = account_db.query(UmGroup).filter(
        UmGroup.id == group_id,
        UmGroup.account_id == account_id,
    ).first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Group {group_id} not found")
    return group
