from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
)
from sqlalchemy.sql import func

from app.database import SystemBase


class DevSession(SystemBase):
    """Dev session model — tracks an AI agent coding session for an App.

    One App can have multiple sessions.
    Each session is bound to exactly ONE agent (pi | opencode | antigravity).
    The agent cannot be changed during the session.
    Each session maps to an underlying native agent session (external_session_id)
    and a background tmux session (tmux_session_name) inside the dev container.
    """

    __tablename__ = "dev_sessions"
    __table_args__ = {"schema": "apps"}

    id = Column(
        String(32),
        primary_key=True,
        default=lambda: f"sess_{uuid.uuid4().hex[:16]}",
    )
    app_id = Column(String(64), nullable=False, index=True)
    workspace_id = Column(String(64), nullable=True)
    title = Column(String(256), nullable=False)
    agent = Column(String(32), nullable=False)  # 'pi' | 'opencode' | 'antigravity' (IMMUTABLE)
    external_session_id = Column(String(128), nullable=True)  # Native CLI session UUID / ID
    tmux_session_name = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="active")  # 'active' | 'idle' | 'stopped' | 'archived'
    model = Column(String(128), nullable=True)  # Bound AI model, e.g. 'gpt-5.4-mini'
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
