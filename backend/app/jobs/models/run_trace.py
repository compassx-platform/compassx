"""
Jobs module — run/task-run models.

Tables (all in schema: jobs, DB: compassx_system via SystemBase):
  jobs.job_runs   — one row per dag_run (manual, scheduled, or rerun)
  jobs.task_runs  — one row per task-instance attempt (retry = new row, same dag_run_id)
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

class TriggerType(str, enum.Enum):
    scheduled = "scheduled"
    manual    = "manual"
    rerun     = "rerun"


class RunState(str, enum.Enum):
    queued      = "queued"
    running     = "running"
    success     = "success"
    failed      = "failed"
    up_for_retry = "up_for_retry"
    cancelled   = "cancelled"


class TaskRunState(str, enum.Enum):
    queued          = "queued"
    running         = "running"
    success         = "success"
    failed          = "failed"
    up_for_retry    = "up_for_retry"
    upstream_failed = "upstream_failed"
    skipped         = "skipped"


# ── JobRun ────────────────────────────────────────────────────────────────────

class JobRun(Base):
    """One row per dag_run. trigger_type distinguishes manual, scheduled, rerun."""
    __tablename__ = "job_runs"
    __table_args__ = (
        Index("idx_job_runs_job_id", "job_id"),
        Index("idx_job_runs_state", "state"),
        Index("idx_job_runs_started_at", "started_at"),
        {"schema": "jobs"},
    )

    job_run_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id            = Column(UUID(as_uuid=True), ForeignKey("jobs.jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    job_version       = Column(Integer, nullable=True)
    dag_run_id        = Column(Text, nullable=True)   # Airflow dag_run_id for correlation
    trigger_type      = Column(
        Enum(TriggerType, name="trigger_type", schema="jobs"),
        nullable=False,
        default=TriggerType.manual,
        server_default="manual",
    )
    triggered_by      = Column(Text, nullable=True)       # user id / email; null for scheduled
    parent_job_run_id = Column(UUID(as_uuid=True), nullable=True)  # set on rerun
    state             = Column(
        Enum(RunState, name="run_state", schema="jobs"),
        nullable=False,
        default=RunState.queued,
        server_default="queued",
    )
    started_at      = Column(DateTime(timezone=True), nullable=True)
    ended_at        = Column(DateTime(timezone=True), nullable=True)
    last_synced_at  = Column(DateTime(timezone=True), nullable=True, default=_utcnow)

    # relationships
    job       = relationship(
        "Job", back_populates="runs",
        foreign_keys=[job_id],
    )
    task_runs = relationship("TaskRun", back_populates="job_run", cascade="all, delete-orphan")


# ── TaskRun ───────────────────────────────────────────────────────────────────

class TaskRun(Base):
    """
    One row per task-instance attempt.
    Retry (task-instance clear) → same dag_run_id, incremented try_number, new row.
    Rerun (new dag_run) → new job_run_id, new rows for all tasks.
    """
    __tablename__ = "task_runs"
    __table_args__ = (
        Index("idx_task_runs_job_run_id", "job_run_id"),
        Index("idx_task_runs_state", "state"),
        Index("idx_task_runs_task_key", "task_key"),
        UniqueConstraint(
            "dag_run_id", "airflow_task_id", "try_number",
            name="uq_task_runs_airflow_attempt",
        ),
        {"schema": "jobs"},
    )

    task_run_id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_run_id      = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_runs.job_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    task_key        = Column(Text, nullable=False)   # matches task_definitions[].task_key
    dag_run_id      = Column(Text, nullable=True)
    airflow_task_id = Column(Text, nullable=True)
    try_number      = Column(Integer, nullable=False, default=1, server_default="1")
    state           = Column(
        Enum(TaskRunState, name="task_run_state", schema="jobs"),
        nullable=False,
        default=TaskRunState.queued,
        server_default="queued",
    )
    execution_ref = Column(Text, nullable=True)   # id of underlying notebook/query run
    started_at    = Column(DateTime(timezone=True), nullable=True)
    ended_at      = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True, default=_utcnow)

    job_run = relationship("JobRun", back_populates="task_runs")


class ExecutionToken(Base):
    """Single-use task-scoped credential exchanged by an Airflow operator."""

    __tablename__ = "execution_tokens"
    __table_args__ = (
        Index("idx_execution_tokens_job_run", "job_run_id"),
        {"schema": "jobs"},
    )

    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_runs.job_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    task_key = Column(Text, nullable=False)
    token_hash = Column(Text, nullable=True)
    scoped_user_id = Column(Text, nullable=True)
    scoped_workspace_id = Column(UUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    exchanged_at = Column(DateTime(timezone=True), nullable=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class JobExecution(Base):
    """Execution record for code dispatched outside the Airflow worker."""

    __tablename__ = "job_executions"
    __table_args__ = (
        Index("idx_job_executions_task_run", "task_run_id"),
        Index("idx_job_executions_state", "state"),
        UniqueConstraint("task_run_id", name="uq_job_executions_task_run"),
        {"schema": "jobs"},
    )

    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.task_runs.task_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    runtime_id = Column(Text, nullable=True)
    state = Column(String(20), nullable=False, default="queued", server_default="queued")
    output_uri = Column(Text, nullable=True)
    logs = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)


class SyncCorrection(Base):
    """Audit row written when poll reconciliation corrects callback state."""

    __tablename__ = "sync_corrections"
    __table_args__ = (
        Index("idx_sync_corrections_job_run", "job_run_id"),
        {"schema": "jobs"},
    )

    correction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.job_runs.job_run_id", ondelete="CASCADE"),
        nullable=False,
    )
    task_run_id = Column(UUID(as_uuid=True), nullable=True)
    previous_state = Column(String(30), nullable=True)
    corrected_state = Column(String(30), nullable=False)
    source = Column(String(30), nullable=False, default="airflow_poll")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
