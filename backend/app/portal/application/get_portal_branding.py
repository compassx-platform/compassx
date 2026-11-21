"""Public portal mark for the sign-in screen.

Returns only the configured logo. Sidebar layout and other settings stay private.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.portal_config import PortalConfig
from app.schemas.portal_config import PortalSettings


def get_portal_branding(workspace_slug: str, sdb: Session) -> PortalSettings:
    slug = (workspace_slug or "").strip()
    if not slug:
        return PortalSettings(logo=None)
    cfg = sdb.query(PortalConfig).filter(PortalConfig.workspace_slug == slug).first()
    stored = cfg.settings if cfg is not None and isinstance(getattr(cfg, "settings", None), dict) else {}
    return PortalSettings(logo=stored.get("logo") or None)
