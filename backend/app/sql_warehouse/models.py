import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import SystemBase as Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqlWarehouse(Base):
    __tablename__ = "sql_warehouse_warehouses"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_sql_warehouse_name_workspace"),
        {"schema": "compute"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="duckdb")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped", index=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resource_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SqlQueryRecord(Base):
    __tablename__ = "history"
    __table_args__ = {"schema": "query"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    sql_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    engine: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, default="sql_editor", index=True)
    dashboard_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    dataset_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_by_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    run_by_user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rows_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_scanned: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)


class SqlActiveQuery(Base):
    __tablename__ = "active_queries"
    __table_args__ = {"schema": "query"}

    query_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    engine_query_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class SqlDraftQuery(Base):
    __tablename__ = "draft_queries"
    __table_args__ = (
        Index("idx_draft_queries_user_ws", "user_id", "workspace_id", "tab_order"),
        {"schema": "query"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Query 1")
    sql_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    catalog: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default="")
    tab_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

