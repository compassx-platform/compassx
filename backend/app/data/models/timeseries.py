"""SQLAlchemy models for time-series data editor module.

Tables:
  - raw_data          (existing table, mapped read/write)
  - tag_definitions   (new – canonical tag registry)
  - upload_staging    (new – staging area for uploaded batches)
  - timeseries_edit_log (new – audit trail for all value changes)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Double,
    Float,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import RawBase as Base


def _utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Existing table – raw_data
# We map it so SQLAlchemy can query / upsert without raw SQL.
# The UNIQUE constraint (ts, asset_id, tag_def_id) must be added via migration.
# ---------------------------------------------------------------------------
class RawData(Base):
    __tablename__ = "raw_data"
    __table_args__ = (
        UniqueConstraint("ts", "asset_id", "tag_def_id", name="uq_raw_data_ts_asset_tag"),
        Index("idx_raw_data_asset_tag_ts", "asset_id", "tag_def_id", "ts"),
        # No schema prefix needed – raw_engine connects directly to landing_zone DB
        # where raw_data lives in the default public schema.
        {"extend_existing": True},
    )

    # Composite PK via ts + asset_id + tag_def_id (no surrogate key in original)
    ts = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    asset_id = Column(BigInteger, primary_key=True, nullable=False)
    tag_def_id = Column(Integer, primary_key=True, nullable=False)
    tag_def_name = Column(Text, nullable=True)   # temporary column, will be removed later
    value = Column(Double, nullable=True)


# ---------------------------------------------------------------------------
# Tag definitions – canonical registry seeded from raw_data.tag_def_name
# ---------------------------------------------------------------------------
class TagDefinition(Base):
    __tablename__ = "tag_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)


# ---------------------------------------------------------------------------
# Upload staging – one row per uploaded data row, per batch
# ---------------------------------------------------------------------------
class UploadStaging(Base):
    __tablename__ = "upload_staging"
    __table_args__ = (
        Index("idx_staging_batch_id", "batch_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # batch_id remains UUID – it is a session correlation token, not a DB entity ID
    batch_id = Column(UUID(as_uuid=True), nullable=False)
    row_number = Column(Integer, nullable=False)

    # Raw values as parsed from the file
    ts = Column(DateTime(timezone=True), nullable=True)
    asset_ref = Column(Text, nullable=True)   # raw text from file (name or id)
    tag_ref = Column(Text, nullable=True)     # raw text from file (name or id)
    value = Column(Double, nullable=True)

    # Resolved IDs (populated during validation)
    asset_id = Column(BigInteger, nullable=True)
    tag_def_id = Column(Integer, nullable=True)

    # Validation outcome
    status = Column(Text, default="pending")   # pending / valid / invalid / duplicate
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Edit log – immutable audit trail for every value change
# ---------------------------------------------------------------------------
class TimeseriesEditLog(Base):
    __tablename__ = "timeseries_edit_log"
    __table_args__ = (
        Index("idx_edit_log_ts_asset_tag", "ts", "asset_id", "tag_def_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False)
    asset_id = Column(BigInteger, nullable=False)
    tag_def_id = Column(Integer, nullable=False)
    old_value = Column(Double, nullable=True)
    new_value = Column(Double, nullable=True)
    updated_by = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow)
    source = Column(Text, nullable=True)   # 'inline' | 'upload'