"""User Manager — /api/um/setup/* routes (§5.1).

GET  /api/um/setup/status   → { needs_setup: bool }
POST /api/um/setup/complete → spans both DBs, returns access+refresh tokens
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/um/setup", tags=["setup"])


# ── Schemas ───────────────────────────────────────────────────────────────────

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


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=SetupStatusOut)
def setup_status(account_db: Session = Depends(get_account_db)):
    """Check whether initial setup has been completed."""
    from app.workspace.models import Account
    account = account_db.query(Account).first()
    if account is None:
        return {"needs_setup": True}
    # Check setup_completed column if it exists
    setup_completed = getattr(account, "setup_completed", None)
    if setup_completed is None:
        # Column doesn't exist yet; check if any UmUser exists as proxy
        user_count = account_db.query(UmUser).count()
        return {"needs_setup": user_count == 0}
    return {"needs_setup": not setup_completed}


@router.post("/complete", response_model=SetupCompleteOut, status_code=201)
def setup_complete(
    body: SetupCompleteIn,
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """One-time setup: create account, admin user, first workspace, seed static tables.

    Guards against concurrent double-submit by checking existing users.
    Once a UmUser exists, returns 403 permanently.
    """
    # Guard: already set up?
    existing_user = account_db.query(UmUser).filter(UmUser.account_id != None).first()
    if existing_user:
        raise HTTPException(status_code=403, detail="Setup already completed")

    # 1. Ensure seed data (account_roles, workspace_roles, landing_rules, etc.)
    run_all_seeds(account_db, system_db)

    # 2. Get or create Account in account_db
    from app.workspace.models import Account, Workspace as LegacyWorkspace
    account = account_db.query(Account).first()
    if account is None:
        import uuid
        account = Account(
            id=str(uuid.uuid4()),
            name=body.account_name,
            slug=body.account_name.lower().replace(" ", "-"),
        )
        account_db.add(account)
        account_db.flush()

    account_id = account.id

    # 3. Create admin UmUser
    admin_user = UmUser(
        account_id=account_id,
        email=body.admin_email.lower().strip(),
        display_name=body.admin_display_name,
        password_hash=hash_password(body.admin_password),
        auth_provider="local",
        status="active",
    )
    account_db.add(admin_user)
    account_db.flush()

    # 4. Assign account_admin role
    account_db.add(UmAccountRoleAssignment(
        account_id=account_id,
        principal_id=admin_user.id,
        principal_type="user",
        role_id="account_admin",
        granted_by=admin_user.id,
    ))
    account_db.flush()

    # 5. Create workspace if requested (otherwise workspace creation flow will kick in post-setup)
    ws_id = None
    if body.workspace_name:
        ws_id = str(__import__("uuid").uuid4())
        try:
            legacy_ws = LegacyWorkspace(
                id=ws_id,
                account_id=account_id,
                name=body.workspace_name,
                slug=body.workspace_name.lower().replace(" ", "-"),
                storage_backend="local",
                storage_config={},
                created_by=admin_user.id,
            )
            account_db.add(legacy_ws)
            account_db.flush()

            system_db.add(UmWorkspaceRoleAssignment(
                workspace_id=ws_id,
                principal_id=admin_user.id,
                principal_type="user",
                role_id="workspace_admin",
                is_default=True,
                granted_by=admin_user.id,
            ))
            system_db.flush()
        except Exception as ws_err:
            logger.warning("Could not create initial workspace: %s", ws_err)

    # 7. Issue tokens
    access_token = create_access_token(
        user_id=admin_user.id,
        account_id=account_id,
        account_roles=["account_admin"],
    )
    raw_refresh = generate_refresh_token()
    account_db.add(UmRefreshToken(
        user_id=admin_user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
    ))

    account_db.commit()
    system_db.commit()

    logger.info("Setup complete: account=%s, admin=%s, workspace=%s", account_id, admin_user.id, ws_id)

    return SetupCompleteOut(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=admin_user.id,
        account_id=account_id,
    )
