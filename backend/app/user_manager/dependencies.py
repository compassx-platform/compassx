"""User Manager — FastAPI dependency injection helpers.

Provides:
  get_current_um_user  — validates JWT, returns UmUser (raises 401 if invalid)
  require_account_admin — 403 if user isn't account_admin
  require_workspace_access — 403 if user has no access to a workspace
  get_effective_account_role — resolves highest-privilege account role for a user
  ROLE_RANK — ordered dict for role comparison
"""
from __future__ import annotations

import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_account_db, get_system_db
from app.user_manager.models.account_models import UmUser, UmAccountRoleAssignment
from app.user_manager.models.system_models import UmWorkspaceRoleAssignment
from app.user_manager.auth_utils import decode_access_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role rank table — higher index = higher privilege
# Used for tie-breaking when a principal holds a role via multiple paths
# ---------------------------------------------------------------------------
ACCOUNT_ROLE_RANK: dict[str, int] = {
    "account_admin":   100,
    "billing_admin":    50,
    "account_viewer":   10,
}

WORKSPACE_ROLE_RANK: dict[str, int] = {
    "workspace_admin":  100,
    "analyst":           50,
    "business_viewer":   10,
}

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Core: extract user from JWT
# ---------------------------------------------------------------------------

def get_current_um_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_account_db),
) -> UmUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(UmUser).filter(UmUser.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status in ("suspended", "deactivated"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Account is {user.status}")

    return user


# ---------------------------------------------------------------------------
# Get effective (highest-privilege) account role for a user
# ---------------------------------------------------------------------------

def get_effective_account_role(user_id: str, account_id: str, db: Session) -> str | None:
    """Return the highest-ranked account role the user holds (directly or via group)."""
    rows = (
        db.query(UmAccountRoleAssignment)
        .filter(
            UmAccountRoleAssignment.principal_id == user_id,
            (UmAccountRoleAssignment.account_id == account_id) | (UmAccountRoleAssignment.account_id.is_(None))
        )
        .all()
    )
    if not rows:
        rows = (
            db.query(UmAccountRoleAssignment)
            .filter(UmAccountRoleAssignment.principal_id == user_id)
            .all()
        )
    if not rows:
        return None
    best = max(rows, key=lambda r: ACCOUNT_ROLE_RANK.get(r.role_id, 0))
    return best.role_id


# ---------------------------------------------------------------------------
# Require account_admin
# ---------------------------------------------------------------------------

def require_um_account_admin(
    user: UmUser = Depends(get_current_um_user),
    db: Session = Depends(get_account_db),
) -> UmUser:
    role = get_effective_account_role(user.id, user.account_id, db)
    if role != "account_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account admin required")
    return user


# ---------------------------------------------------------------------------
# Get effective workspace role for a user (direct + via group)
# ---------------------------------------------------------------------------

def get_effective_workspace_role(
    user_id: str,
    workspace_id: str,
    system_db: Session,
    account_db: Session,
) -> str | None:
    """Return highest-ranked workspace role the user holds (direct or via group)."""
    from app.user_manager.models.account_models import UmGroupMember

    # Direct assignment
    direct = (
        system_db.query(UmWorkspaceRoleAssignment)
        .filter(
            UmWorkspaceRoleAssignment.workspace_id == workspace_id,
            UmWorkspaceRoleAssignment.principal_id == user_id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        )
        .first()
    )

    # Via group membership
    group_ids = [
        gm.group_id
        for gm in account_db.query(UmGroupMember).filter(UmGroupMember.user_id == user_id).all()
    ]
    group_assignments = []
    if group_ids:
        group_assignments = (
            system_db.query(UmWorkspaceRoleAssignment)
            .filter(
                UmWorkspaceRoleAssignment.workspace_id == workspace_id,
                UmWorkspaceRoleAssignment.principal_id.in_(group_ids),
                UmWorkspaceRoleAssignment.principal_type == "group",
            )
            .all()
        )

    all_assignments = ([direct] if direct else []) + group_assignments
    if not all_assignments:
        return None

    best = max(all_assignments, key=lambda a: WORKSPACE_ROLE_RANK.get(a.role_id, 0))
    return best.role_id


# ---------------------------------------------------------------------------
# Require workspace admin (own workspace) or account admin
# ---------------------------------------------------------------------------

def require_workspace_admin(workspace_id: str, user: UmUser, account_db: Session, system_db: Session) -> None:
    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    if account_role == "account_admin":
        return
    ws_role = get_effective_workspace_role(user.id, workspace_id, system_db, account_db)
    if ws_role != "workspace_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace admin required")
