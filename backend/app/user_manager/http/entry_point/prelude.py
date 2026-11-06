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
