"""Save portal-only preferences without changing the sidebar layout."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.portal_config import PortalConfig
from app.portal.application.workspace_items import selected_workspace_id
from app.schemas.portal_config import PortalSettings, PortalSettingsUpdate

LOGO_PREFIXES = (
    "data:image/png",
    "data:image/jpeg",
    "data:image/jpg",
    "data:image/webp",
    "data:image/gif",
    "data:image/svg+xml",
)
MAX_LOGO_CHARS = 700_000


def _clean_logo(logo: Optional[str]) -> Optional[str]:
    if logo is None:
        return None
    value = logo.strip()
    if not value:
        return None
    head = value.split(",", 1)[0].lower()
    if not any(head.startswith(prefix) for prefix in LOGO_PREFIXES):
        raise HTTPException(status_code=400, detail="The logo must be a PNG, JPEG, WebP, GIF, or SVG image.")
    if len(value) > MAX_LOGO_CHARS:
        raise HTTPException(status_code=400, detail="The logo is too large. Use an image under 400 KB.")
    return value


def update_portal_settings(
    body: PortalSettingsUpdate,
    request: Request,
    workspace_id: Optional[str],
    workspace_slug: Optional[str],
    sdb: Session,
    guard,
    adb: Session = None,
) -> PortalSettings:
    principal = getattr(guard, "principal", None)
    role = principal.workspace_role(guard.workspace_id) if principal is not None else None
    if role != "admin":
        guard.require_workspace_admin("Saving portal settings")

    target_ws = selected_workspace_id(workspace_id, workspace_slug, guard, adb) or "default"
    cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_id == target_ws).first()
    logo = _clean_logo(body.logo)

    if not cfg:
        cfg = PortalConfig(
            id=f"portal_cfg_{uuid.uuid4().hex[:16]}",
            workspace_id=target_ws,
            workspace_slug=workspace_slug,
            sections=[],
            settings={"logo": logo},
            created_by_user_id=getattr(guard, "user_id", None),
        )
        sdb.add(cfg)
    else:
        current = dict(cfg.settings or {})
        current["logo"] = logo
        cfg.settings = current
        flag_modified(cfg, "settings")

    sdb.commit()
    sdb.refresh(cfg)
    stored = cfg.settings if isinstance(cfg.settings, dict) else {}
    return PortalSettings(logo=stored.get("logo") or None)
