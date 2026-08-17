"""User Manager — /entry-point route (§4, §7 frontend contract).

GET /api/um/entry-point?deep_link_workspace_id=<uuid>
Auth: required (access token)
Response: { workspace_id: UUID | null, section: str, route: str }
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_account_db, get_system_db
from app.user_manager.dependencies import get_current_um_user
from app.user_manager.entry_point import resolve_entry_point
from app.user_manager.models.account_models import UmUser
from pydantic import BaseModel

router = APIRouter(prefix="/api/um", tags=["um-entry-point"])


class EntryPointOut(BaseModel):
    workspace_id: str | None
    section: str
    route: str


@router.get("/entry-point", response_model=EntryPointOut)
def entry_point(
    deep_link_workspace_id: str | None = Query(None),
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Resolve post-login landing per §4. Called once per session bootstrap."""
    result = resolve_entry_point(
        user_id=user.id,
        account_db=account_db,
        system_db=system_db,
        deep_link_workspace_id=deep_link_workspace_id,
    )
    return EntryPointOut(**result)
