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

import app.user_manager.http.entry_point.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.user_manager.http.entry_point.application.entry_point import entry_point as entry_point_action

router = APIRouter(prefix="/api/um", tags=["um-entry-point"])


@router.get("/entry-point", response_model=EntryPointOut)
def entry_point(
    deep_link_workspace_id: str | None = Query(None),
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Resolve post-login landing per §4. Called once per session bootstrap."""
    return entry_point_action(deep_link_workspace_id=deep_link_workspace_id, user=user, account_db=account_db, system_db=system_db)
