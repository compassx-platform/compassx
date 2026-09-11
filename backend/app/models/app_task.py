from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import SystemBase


class AppTask(SystemBase):
    """Application Task tracking model stored in the system database under the 'apps' schema.

    Each task is scoped to a specific application and workspace, supporting
    Kanban lifecycle stages (backlog, in_progress, testing, waiting_for_deployment, completed).
    """
    __tablename__ = "app_tasks"
    __table_args__ = {"schema": "apps"}

    id = Column(
        String(32),
        primary_key=True,
        default=lambda: f"task_{uuid.uuid4().hex[:16]}",
    )
    app_id = Column(String(64), nullable=False, index=True)
    workspace_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(64), nullable=False, default="backlog", index=True)
    priority = Column(String(32), nullable=False, default="medium")
    tags = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    assignee = Column(String(128), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    order = Column(Integer, nullable=False, default=0)

    created_by_user_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
