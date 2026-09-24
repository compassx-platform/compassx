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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/portal", tags=["Portal"])


def _bootstrap_default_config(
    workspace_id: str,
    workspace_slug: Optional[str],
    sdb: Session,
    adb: Session,
    user_id: Optional[str] = None,
) -> PortalConfig:
    """Build a sensible default portal configuration using existing apps & dashboards."""
    # Query workspace apps
    app_query = sdb.query(App)
    if workspace_id:
        app_query = app_query.filter(App.workspace_id == workspace_id)
    elif workspace_slug:
        app_query = app_query.filter(App.workspace_slug == workspace_slug)
    apps = app_query.order_by(App.created_at.desc()).all()

    # Query dashboards
    dashboards = adb.query(Dashboard).order_by(Dashboard.created_at.desc()).all()

    sections: List[dict] = []

    # Apps Section
    app_items = []
    for idx, a in enumerate(apps):
        app_items.append({
            "id": f"item_app_{a.id}",
            "type": "app",
            "target_id": a.id,
            "title": a.name,
            "icon": "LayoutGrid" if a.app_type == "react" else "Sparkles" if a.app_type == "streamlit" else "Code2",
            "is_visible": True,
            "order": idx,
            "url": a.route,
            "app_type": a.app_type,
            "status": a.status,
        })

    if app_items:
        sections.append({
            "id": "sec_applications",
            "title": "Applications",
            "items": app_items,
        })

    # Dashboards Section
    dash_items = []
    for idx, d in enumerate(dashboards):
        dash_items.append({
            "id": f"item_dash_{d.id}",
            "type": "dashboard",
            "target_id": str(d.id),
            "title": d.name,
            "icon": "BarChart2",
            "is_visible": True,
            "order": idx,
            "url": None,
            "app_type": None,
            "status": "published" if not d.is_draft else "draft",
        })

    if dash_items:
        sections.append({
            "id": "sec_dashboards",
            "title": "Dashboards",
            "items": dash_items,
        })

    # Fallback if both empty
    if not sections:
        sections.append({
            "id": "sec_applications",
            "title": "Applications",
            "items": [],
        })

    new_cfg = PortalConfig(
        id=f"portal_cfg_{uuid.uuid4().hex[:16]}",
        workspace_id=workspace_id or "default",
        workspace_slug=workspace_slug,
        sections=sections,
        created_by_user_id=user_id,
    )
    sdb.add(new_cfg)
    try:
        sdb.commit()
        sdb.refresh(new_cfg)
    except Exception as e:
        sdb.rollback()
        logger.warning("Could not persist auto-bootstrapped portal config: %s", e)

    return new_cfg


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
    target_ws = workspace_id or guard.workspace_id or "default"
    cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_id == target_ws).first()

    if not cfg and workspace_slug:
        cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_slug == workspace_slug).first()

    if not cfg:
        cfg = _bootstrap_default_config(
            workspace_id=target_ws,
            workspace_slug=workspace_slug,
            sdb=sdb,
            adb=adb,
            user_id=guard.user_id if hasattr(guard, "user_id") else None,
        )

    return PortalConfigOut(
        id=cfg.id,
        workspace_id=cfg.workspace_id,
        workspace_slug=cfg.workspace_slug,
        sections=cfg.sections or [],
        updated_at=cfg.updated_at or cfg.created_at,
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
    target_ws = workspace_id or guard.workspace_id or "default"
    cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_id == target_ws).first()

    sections_data = [sec.dict() for sec in body.sections]

    if not cfg:
        cfg = PortalConfig(
            id=f"portal_cfg_{uuid.uuid4().hex[:16]}",
            workspace_id=target_ws,
            workspace_slug=workspace_slug,
            sections=sections_data,
            created_by_user_id=guard.user_id if hasattr(guard, "user_id") else None,
        )
        sdb.add(cfg)
    else:
        cfg.sections = sections_data
        if workspace_slug:
            cfg.workspace_slug = workspace_slug
        cfg.updated_at = datetime.now(timezone.utc)
        flag_modified(cfg, "sections")

    sdb.commit()
    sdb.refresh(cfg)

    return PortalConfigOut(
        id=cfg.id,
        workspace_id=cfg.workspace_id,
        workspace_slug=cfg.workspace_slug,
        sections=cfg.sections or [],
        updated_at=cfg.updated_at or cfg.created_at,
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
    target_ws = workspace_id or guard.workspace_id
    app_query = sdb.query(App)
    if target_ws:
        app_query = app_query.filter(App.workspace_id == target_ws)
    elif workspace_slug:
        app_query = app_query.filter(App.workspace_slug == workspace_slug)

    apps = app_query.order_by(App.created_at.desc()).all()
    dashboards = adb.query(Dashboard).order_by(Dashboard.created_at.desc()).all()

    app_list = [
        AvailableAppItem(
            id=a.id,
            name=a.name,
            slug=a.slug,
            description=a.description,
            app_type=a.app_type,
            status=a.status,
            route=a.route,
        )
        for a in apps
    ]

    dash_list = [
        AvailableDashboardItem(
            id=str(d.id),
            name=d.name,
            description=None,
            is_draft=bool(d.is_draft),
            published_at=d.published_at,
        )
        for d in dashboards
    ]

    return PortalAvailableItemsResponse(
        apps=app_list,
        dashboards=dash_list,
    )
