"""Portal routes: /api/v1/portal/...

Provides workspace-scoped portal navigation configuration, available items
(apps & dashboards) for sidebar customization, and layout persistence.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_system_db, get_account_db
from app.governance.dependencies import Guard, get_guard
from app.models.app import App
from app.models.dashboard import Dashboard
from app.models.portal_config import PortalConfig
from app.schemas.portal_config import (
    AvailableAppItem,
    AvailableDashboardItem,
    PortalAvailableItemsResponse,
    PortalConfigOut,
    PortalConfigUpdate,
    PortalItem,
    PortalSection,
)

import app.portal.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

from app.portal.application.get_portal_config import _bootstrap_default_config
from app.portal.application.get_portal_config import get_portal_config as get_portal_config_action
from app.portal.application.update_portal_config import update_portal_config as update_portal_config_action
from app.portal.application.get_available_items import get_available_items as get_available_items_action

logger = logging.getLogger("app.routes.portal_routes")

router = APIRouter(prefix="/api/v1/portal", tags=["Portal"])


@router.get("/config", response_model=PortalConfigOut)
def get_portal_config(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    adb: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve the portal configuration for the specified workspace.

    If no configuration exists, automatically bootstraps one from the workspace's
    deployed apps and dashboards.
    """
    return get_portal_config_action(
        request=request,
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        sdb=sdb,
        adb=adb,
        guard=guard,
    )


@router.put("/config", response_model=PortalConfigOut)
def update_portal_config(
    body: PortalConfigUpdate,
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Save updated portal navigation layout (sections, items, ordering, icons, visibility)."""
    return update_portal_config_action(
        body=body,
        request=request,
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        sdb=sdb,
        guard=guard,
    )


@router.get("/available-items", response_model=PortalAvailableItemsResponse)
def get_available_items(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    sdb: Session = Depends(get_system_db),
    adb: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve all candidate apps and dashboards available to be pinned/linked into the Portal."""
    return get_available_items_action(
        request=request,
        workspace_id=workspace_id,
        workspace_slug=workspace_slug,
        sdb=sdb,
        adb=adb,
        guard=guard,
    )
