from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import SystemBase


class PortalConfig(SystemBase):
    """Workspace Portal layout and navigation configuration.

    Stores sections, item order, icons, visibility, and custom links for the
    centralized business consumption portal.
    """
    __tablename__ = "portal_configs"
    __table_args__ = {"schema": "apps"}

    id = Column(
        String(64),
        primary_key=True,
        default=lambda: f"portal_cfg_{uuid.uuid4().hex[:16]}",
    )
    workspace_id = Column(String(64), nullable=False, unique=True, index=True)
    workspace_slug = Column(String(128), nullable=True, index=True)
    
    # List of sections containing items (apps, dashboards, external links)
    sections = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)

    created_by_user_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
