"""
Jobs module — core entity models.

Tables (all in schema: jobs, DB: compassx_system via SystemBase):
  jobs.jobs             — canonical job entity
  jobs.job_versions     — immutable version snapshots (draft & published)
  jobs.airflow_job_specs — denormalised read-model consumed by DAG factory
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index,
    Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import SystemBase as Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    active   = "active"
    paused   = "paused"
    archived = "archived"


# ── Job ───────────────────────────────────────────────────────────────────────

class Job(Base):
    """Canonical job entity — one row per job, holds status and version pointers."""
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_workspace_id", "workspace_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_owner", "owner_user_id"),
        {"schema": "jobs"},
    )

    job_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id    = Column(UUID(as_uuid=True), nullable=True, index=True)
    name            = Column(Text, nullable=False)
    description     = Column(Text, nullable=True)
    owner_user_id   = Column(Text, nullable=True)
    current_version = Column(Integer, nullable=True)      # points to published job_version_id row (version_number)
    draft_version   = Column(Integer, nullable=True)      # points to unpublished draft (version_number), null if none
    status          = Column(
        Enum(JobStatus, name="job_status", schema="jobs"),
        nullable=False,
        default=JobStatus.active,
        server_default="active",
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    versions = relationship("JobVersion", back_populates="job", cascade="all, delete-orphan", lazy="dynamic")
    runs     = relationship("JobRun",     back_populates="job", cascade="all, delete-orphan", lazy="dynamic")
    spec     = relationship("AirflowJobSpec", back_populates="job", uselist=False, cascade="all, delete-orphan", foreign_keys="AirflowJobSpec.job_id")


# ── JobVersion ────────────────────────────────────────────────────────────────

class JobVersion(Base):
    """
    Immutable snapshot of a job's configuration at a specific version.
    task_definitions is a JSONB array of task specs; kept denormalised to avoid
    version-fanout across a sibling tasks table.
    """
    __tablename__ = "job_versions"
    __table_args__ = (
        Index("idx_jv_job_id", "job_id"),
        Index("idx_jv_job_version", "job_id", "version_number", unique=True),
        {"schema": "jobs"},
    )

    job_version_id  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id          = Column(UUID(as_uuid=True), ForeignKey("jobs.jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number  = Column(Integer, nullable=False)
    schedule_cron   = Column(Text, nullable=True)              # null → manual only
    timezone        = Column(String(100), nullable=False, default="UTC", server_default="UTC")
    max_active_runs = Column(Integer, nullable=False, default=1, server_default="1")
    retry_policy    = Column(JSONB, nullable=False, default=dict, server_default="{}")
    task_definitions = Column(JSONB, nullable=False, default=list, server_default="[]")
    is_published    = Column(Boolean, nullable=False, default=False, server_default="false")
    published_at    = Column(DateTime(timezone=True), nullable=True)
    published_by    = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by      = Column(Text, nullable=True)

    job = relationship("Job", back_populates="versions")


# ── AirflowJobSpec ───────────────────────────────────────────────────────────

class AirflowJobSpec(Base):
    """
    Flat, join-free read-model consumed by the DAG factory at parse time.
    Written only at publish time. Never queried with joins.
    """
    __tablename__ = "airflow_job_specs"
    __table_args__ = (
        Index("idx_ajs_is_active", "is_active"),
        {"schema": "jobs"},
    )

    job_id          = Column(UUID(as_uuid=True), ForeignKey("jobs.jobs.job_id", ondelete="CASCADE"), primary_key=True)
    dag_id          = Column(Text, nullable=False)
    job_version     = Column(Integer, nullable=False)
    workspace_id    = Column(UUID(as_uuid=True), nullable=True)
    schedule_cron   = Column(Text, nullable=True)
    timezone        = Column(String(100), nullable=False, default="UTC", server_default="UTC")
    max_active_runs = Column(Integer, nullable=False, default=1, server_default="1")
    retry_policy    = Column(JSONB, nullable=False, default=dict, server_default="{}")
    resolved_tasks  = Column(JSONB, nullable=False, default=list, server_default="[]")
    is_active       = Column(Boolean, nullable=False, default=True, server_default="true")
    spec_checksum   = Column(Text, nullable=True)
    publish_state   = Column(String(20), nullable=False, default="publishing", server_default="publishing")
    airflow_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at      = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    job = relationship("Job", back_populates="spec", foreign_keys=[job_id])
