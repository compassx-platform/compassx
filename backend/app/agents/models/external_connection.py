"""Data models for External Connections and Tool Invocation Audit Logs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB

from app.database import SystemBase as Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    return str(uuid.uuid4())


class ExternalConnection(Base):
    """Workspace-scoped external connection (e.g. Loki log server, REST API)."""

    __tablename__ = "external_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_external_connections_ws_name"),
        Index("idx_external_connections_ws", "workspace_id"),
        {"schema": "ai"},
    )

    id = Column(String(36), primary_key=True, default=_uuid_str)
    workspace_id = Column(String(36), nullable=True)
    name = Column(String(255), nullable=False)
    connector_type = Column(String(100), nullable=False, default="custom")  # e.g. loki, prometheus, custom
    base_url = Column(Text, nullable=False)
    auth_config = Column(Text, nullable=True)  # Fernet encrypted ciphertext storing json / dict
    created_by = Column(String(255), nullable=False, default="default_user")
    status = Column(String(50), nullable=False, default="active")  # active | disabled
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class ToolInvocationAuditLog(Base):
    """Audit log row written on every tool invocation regardless of outcome."""

    __tablename__ = "tool_invocation_audit_log"
    __table_args__ = (
        Index("idx_tool_audit_tool", "tool_id"),
        Index("idx_tool_audit_session", "session_id"),
        {"schema": "ai"},
    )

    id = Column(String(36), primary_key=True, default=_uuid_str)
    tool_id = Column(String(36), nullable=True)
    tool_version_id = Column(String(36), nullable=True)
    connection_id = Column(String(36), nullable=True)
    session_id = Column(String(100), nullable=True)
    agent_type = Column(String(100), nullable=True, default="nova")
    invoked_by = Column(String(255), nullable=True)
    params = Column(JSONB, nullable=True, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    duration_ms = Column(Integer, nullable=False, default=0)
    result_size_bytes = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False)  # success | failure
    error_type = Column(String(100), nullable=True)  # timeout | connection_unreachable | rate_limited | invalid_params | runtime_error
