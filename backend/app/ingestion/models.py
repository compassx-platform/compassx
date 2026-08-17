"""
SQLAlchemy ORM models for the Ingestion module.

All tables live in system_db (the SystemBase metadata / SystemSessionLocal).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

# Reuse the SystemBase declared in database.py so Alembic picks it up correctly.
from app.database import SystemBase


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# credential_secret
# If the Apps feature already created this table Alembic will skip it
# (IF NOT EXISTS guard in the migration).  We still declare the ORM model
# here so FK references work at Python level.
# ---------------------------------------------------------------------------

class CredentialSecret(SystemBase):
    __tablename__ = "credential_secret"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    encrypted_value = Column(LargeBinary, nullable=False)
    encryption_key_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    # back-ref from connections
    connections = relationship("IngestionConnection", back_populates="secret")


# ---------------------------------------------------------------------------
# ingestion_connection
# ---------------------------------------------------------------------------

class IngestionConnection(SystemBase):
    __tablename__ = "ingestion_connection"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    base_url = Column(Text, nullable=False)
    auth_type = Column(Text, nullable=False)  # none|api_key_header|api_key_query|bearer_token|basic_auth
    auth_config = Column(JSONB, nullable=False, default=dict)    # non-secret metadata only
    secret_ref = Column(
        UUID(as_uuid=True),
        ForeignKey("credential_secret.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_headers = Column(JSONB, nullable=False, default=dict)
    rate_limit_rps = Column(Numeric, nullable=False, default=5)
    max_concurrency = Column(Integer, nullable=False, default=5)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    secret = relationship("CredentialSecret", back_populates="connections")
    job_configs = relationship(
        "IngestionJobConfig",
        back_populates="connection",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# ingestion_job_config
# ---------------------------------------------------------------------------

class IngestionJobConfig(SystemBase):
    __tablename__ = "ingestion_job_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_connection.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    http_method = Column(Text, nullable=False, default="GET")
    path_template = Column(Text, nullable=False)
    query_template = Column(JSONB, nullable=False, default=dict)
    body_template = Column(JSONB)

    pagination_type = Column(Text, nullable=False, default="none")
    pagination_config = Column(JSONB, nullable=False, default=dict)

    cursor_field_path = Column(Text)
    cursor_query_param = Column(Text)

    param_source_type = Column(Text, nullable=False, default="static")
    param_source_config = Column(JSONB, nullable=False, default=dict)

    target_bronze_bucket = Column(Text, nullable=False, default="compassx-bronze")
    schedule_cron = Column(Text, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)

    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    connection = relationship("IngestionConnection", back_populates="job_configs")
    watermarks = relationship(
        "IngestionWatermark",
        back_populates="job_config",
        cascade="all, delete-orphan",
    )
    runs = relationship(
        "IngestionRun",
        back_populates="job_config",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# ingestion_watermark
# ---------------------------------------------------------------------------

class IngestionWatermark(SystemBase):
    __tablename__ = "ingestion_watermark"

    job_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_job_config.id", ondelete="CASCADE"),
        primary_key=True,
    )
    param_value = Column(Text, primary_key=True, default="__none__")
    cursor_value = Column(Text)
    last_success_at = Column(DateTime(timezone=True))
    last_run_id = Column(UUID(as_uuid=True))

    job_config = relationship("IngestionJobConfig", back_populates="watermarks")


# ---------------------------------------------------------------------------
# ingestion_run
# ---------------------------------------------------------------------------

class IngestionRun(SystemBase):
    __tablename__ = "ingestion_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_job_config.id", ondelete="CASCADE"),
        nullable=False,
    )
    airflow_dag_run_id = Column(Text)
    status = Column(Text, nullable=False, default="running")  # running|succeeded|failed|partial
    started_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    finished_at = Column(DateTime(timezone=True))
    total_params = Column(Integer, default=0)
    succeeded_params = Column(Integer, default=0)
    failed_params = Column(Integer, default=0)
    total_rows_landed = Column(BigInteger, default=0)
    total_bytes_landed = Column(BigInteger, default=0)
    error_summary = Column(Text)

    job_config = relationship("IngestionJobConfig", back_populates="runs")
    items = relationship(
        "IngestionRunItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# ingestion_run_item
# ---------------------------------------------------------------------------

class IngestionRunItem(SystemBase):
    __tablename__ = "ingestion_run_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    param_value = Column(Text, nullable=False)
    status = Column(Text, nullable=False)  # succeeded|failed|skipped
    pages_fetched = Column(Integer, default=0)
    rows_landed = Column(Integer, default=0)
    bytes_landed = Column(BigInteger, default=0)
    bronze_path = Column(Text)
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    finished_at = Column(DateTime(timezone=True))

    run = relationship("IngestionRun", back_populates="items")
