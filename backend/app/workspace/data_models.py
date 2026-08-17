"""Data plane models for compassx_system database.

All tables here live in the data plane DB.
High-volume tables are range-partitioned by time.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import SystemBase


def _uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# query_history  — partitioned by started_at
# Retention: 90 days
# ---------------------------------------------------------------------------
class QueryHistory(SystemBase):
    __tablename__ = "wp_query_history"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    principal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    warehouse_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    engine: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sql_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_scanned: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Note: actual table is PARTITION BY RANGE (started_at) — created via migration DDL,
    # not via SQLAlchemy create_all (which doesn't support declarative partitioned tables well).
    __table_args__ = {"postgresql_partition_by": "RANGE (started_at)"}


# ---------------------------------------------------------------------------
# agent_run_logs  — partitioned by started_at
# Retention: 180 days
# ---------------------------------------------------------------------------
class AgentRunLog(SystemBase):
    __tablename__ = "wp_agent_run_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    principal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = {"postgresql_partition_by": "RANGE (started_at)"}


# ---------------------------------------------------------------------------
# agent_turn_logs  — partitioned by created_at
# Retention: 180 days
# ---------------------------------------------------------------------------
class AgentTurnLog(SystemBase):
    __tablename__ = "wp_agent_turn_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)

    __table_args__ = {"postgresql_partition_by": "RANGE (created_at)"}


# ---------------------------------------------------------------------------
# wp_llm_call_logs  — partitioned by called_at
# Retention: 90 days
# ---------------------------------------------------------------------------
class WpLlmCallLog(SystemBase):
    __tablename__ = "wp_llm_call_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    component: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)

    __table_args__ = {"postgresql_partition_by": "RANGE (called_at)"}


# ---------------------------------------------------------------------------
# wp_sessions  — not partitioned
# ---------------------------------------------------------------------------
class WpSession(SystemBase):
    __tablename__ = "wp_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


# ---------------------------------------------------------------------------
# wp_sql_warehouses  — not partitioned
# ---------------------------------------------------------------------------
class WpSqlWarehouse(SystemBase):
    __tablename__ = "wp_sql_warehouses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    engine: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="stopped")
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        __import__("sqlalchemy").UniqueConstraint("workspace_id", "name", name="uq_wp_warehouses_workspace_name"),
    )


# ---------------------------------------------------------------------------
# srm_memories  — not partitioned
# ---------------------------------------------------------------------------
class SrmMemory(SystemBase):
    __tablename__ = "wp_srm_memories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
