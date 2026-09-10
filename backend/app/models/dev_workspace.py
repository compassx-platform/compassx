from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    BigInteger,
)
from sqlalchemy.sql import func

from app.database import SystemBase


class DevWorkspace(SystemBase):
    """Dev workspace model — tracks a named subfolder on the shared PVC for a given app.

    Each DevWorkspace maps to a unique directory on the shared PVC:
        /workspaces/{app_id}/{workspace_id}/

    The directory is created on first launch (git clone) and persists across
    pod restarts and stop/start cycles. Multiple workspaces can exist per app,
    each independently tracking a different branch, experiment, or feature.
    """

    __tablename__ = "dev_workspaces"
    __table_args__ = {"schema": "apps"}

    id = Column(
        String(32),
        primary_key=True,
        default=lambda: f"ws_{uuid.uuid4().hex[:16]}",
    )
    app_id = Column(String(64), nullable=False, index=True)
    workspace_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    folder_path = Column(String(512), nullable=False)
    git_branch = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="stopped")  # active | stopped
    size_bytes = Column(BigInteger, nullable=True)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
