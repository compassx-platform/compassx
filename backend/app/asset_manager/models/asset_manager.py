"""SQLAlchemy models for the Asset Manager module."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.database import AssetBase as Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# â”€â”€ Enums â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetCategory(str, enum.Enum):
    SITE = "SITE"
    EQUIPMENT = "EQUIPMENT"
    COMPONENT = "COMPONENT"
    TAG = "TAG"
    EVENT_TYPE = "EVENT_TYPE"


class AssetStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DECOMMISSIONED = "DECOMMISSIONED"
    PLANNED = "PLANNED"
    MAINTENANCE = "MAINTENANCE"


class RelationshipDirection(str, enum.Enum):
    UNIDIRECTIONAL = "UNIDIRECTIONAL"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class EventSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DocumentType(str, enum.Enum):
    MANUAL = "MANUAL"
    CERTIFICATE = "CERTIFICATE"
    DRAWING = "DRAWING"
    REPORT = "REPORT"
    CONTRACT = "CONTRACT"
    OTHER = "OTHER"


class MetadataFieldType(str, enum.Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"
    DATE = "DATE"
    ENUM = "ENUM"
    URL = "URL"
    EMAIL = "EMAIL"
    UOM = "UOM"


# â”€â”€ Asset Type â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetType(Base):
    __tablename__ = "am_asset_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    slug = Column(String(200), nullable=False, unique=True)
    category = Column(Enum(AssetCategory), nullable=False)
    description = Column(Text, nullable=True)
    industry_tags = Column(ARRAY(Text), nullable=False, server_default="{}")
    icon = Column(String(100), nullable=True)
    allowed_parents = Column(ARRAY(Integer), nullable=False, server_default="{}")
    allowed_children = Column(ARRAY(Integer), nullable=False, server_default="{}")
    metadata_schema = Column(JSONB, nullable=False, server_default='{"version": 1, "fields": []}')
    is_root = Column(Boolean, nullable=False, server_default="false")
    is_leaf = Column(Boolean, nullable=False, server_default="false")
    schema_version = Column(Integer, nullable=False, server_default="1")
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    instances = relationship("AssetInstance", back_populates="asset_type", lazy="dynamic")
    tag_definitions = relationship("AssetTypeTag", back_populates="asset_type", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_am_asset_types_slug", "slug"),
        Index("idx_am_asset_types_category", "category"),
    )


# â”€â”€ Asset Instance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetInstance(Base):
    __tablename__ = "am_asset_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_type_id = Column(Integer, ForeignKey("am_asset_types.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=True)
    name = Column(Text, nullable=False)
    code = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(AssetStatus), nullable=False, server_default="ACTIVE")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    commissioned_at = Column(DateTime(timezone=True), nullable=True)
    decommissioned_at = Column(DateTime(timezone=True), nullable=True)
    extra_metadata = Column("metadata", JSONB, nullable=False, server_default="{}")
    metadata_schema_version = Column(Integer, nullable=False, server_default="1")
    path = Column(Text, nullable=False, server_default="/")
    depth = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)

    asset_type = relationship("AssetType", back_populates="instances")
    parent = relationship("AssetInstance", remote_side="AssetInstance.id", foreign_keys=[parent_id])
    children = relationship("AssetInstance", foreign_keys=[parent_id], back_populates="parent")
    versions = relationship("AssetVersion", back_populates="asset", cascade="all, delete-orphan")
    events = relationship("AssetEvent", back_populates="asset", cascade="all, delete-orphan")
    tags = relationship("AssetTag", back_populates="asset", cascade="all, delete-orphan")
    documents = relationship("AssetDocument", back_populates="asset", cascade="all, delete-orphan")
    relationships_from = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.from_asset_id",
        back_populates="from_asset",
        cascade="all, delete-orphan",
    )
    relationships_to = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.to_asset_id",
        back_populates="to_asset",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_am_instances_type_id", "asset_type_id"),
        Index("idx_am_instances_parent_id", "parent_id"),
        Index("idx_am_instances_status", "status"),
        Index("idx_am_instances_path", "path"),
    )


# â”€â”€ Asset Version â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetVersion(Base):
    __tablename__ = "am_asset_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSONB, nullable=False)
    change_summary = Column(Text, nullable=True)
    changed_by = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    asset = relationship("AssetInstance", back_populates="versions")

    __table_args__ = (
        Index("idx_am_versions_asset_version", "asset_id", "version", unique=True),
    )


# â”€â”€ Asset Relationship â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetRelationship(Base):
    __tablename__ = "am_asset_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_asset_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=False)
    to_asset_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=False)
    type = Column(String(100), nullable=False)
    direction = Column(Enum(RelationshipDirection), nullable=False, server_default="UNIDIRECTIONAL")
    extra_metadata = Column("metadata", JSONB, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    created_by = Column(Text, nullable=True)

    from_asset = relationship("AssetInstance", foreign_keys=[from_asset_id], back_populates="relationships_from")
    to_asset = relationship("AssetInstance", foreign_keys=[to_asset_id], back_populates="relationships_to")

    __table_args__ = (
        Index("idx_am_rel_from", "from_asset_id"),
        Index("idx_am_rel_to", "to_asset_id"),
        Index("idx_am_rel_type", "type"),
    )


# â”€â”€ Asset Event â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AssetEvent(Base):
    __tablename__ = "am_asset_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=False)
    linked_assets = Column(ARRAY(Integer), nullable=False, server_default="{}")
    event_type = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(Enum(EventSeverity), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    extra_metadata = Column("metadata", JSONB, nullable=True)
    source = Column(String(100), nullable=True)
    external_ref = Column(String(200), nullable=True)
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    asset = relationship("AssetInstance", back_populates="events")

    __table_args__ = (
        Index("idx_am_events_asset_id", "asset_id"),
        Index("idx_am_events_started_at", "started_at"),
        Index("idx_am_events_type", "event_type"),
        Index("idx_am_events_severity", "severity"),
    )


# ── Asset Type Tag Definition ──────────────────────────────────────────────────

class AssetTypeTag(Base):
    __tablename__ = "am_tags_def"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_type_id = Column(Integer, ForeignKey("am_asset_types.id"), nullable=False)
    tag_key = Column(String(100), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    parameter = Column(String(200), nullable=True)
    unit = Column(String(50), nullable=True)
    is_required = Column(Boolean, nullable=False, server_default="false", default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    asset_type = relationship("AssetType", back_populates="tag_definitions")
    tags = relationship("AssetTag", back_populates="asset_type_tag", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_am_tags_def_type_id", "asset_type_id"),
        Index("idx_am_tags_def_key", "asset_type_id", "tag_key", unique=True),
    )


# ── Asset Tag ────────────────────────────────────────────────────────────────

class AssetTag(Base):
    __tablename__ = "am_asset_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=False)
    asset_type_tag_id = Column(Integer, ForeignKey("am_tags_def.id"), nullable=True)
    tag_id = Column(String(500), nullable=False)
    tag_name = Column(Text, nullable=False)
    parameter = Column(String(200), nullable=True)
    unit = Column(String(50), nullable=True)
    source = Column(String(200), nullable=True)
    is_primary = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    asset = relationship("AssetInstance", back_populates="tags")
    asset_type_tag = relationship("AssetTypeTag", back_populates="tags")

    __table_args__ = (
        Index("idx_am_asset_tags_asset_id", "asset_id"),
        Index("idx_am_asset_tags_asset_tag", "asset_id", "tag_id", unique=True),
        Index("idx_am_asset_tags_type_tag_id", "asset_type_tag_id"),
    )

# ── Asset Document ────────────────────────────────────────────────────────────

class AssetDocument(Base):
    __tablename__ = "am_asset_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey("am_asset_instances.id"), nullable=False)
    title = Column(Text, nullable=False)
    type = Column(Enum(DocumentType), nullable=False, server_default="OTHER")
    url = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    version = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    uploaded_by = Column(Text, nullable=True)

    asset = relationship("AssetInstance", back_populates="documents")

    __table_args__ = (
        Index("idx_am_docs_asset_id", "asset_id"),
        Index("idx_am_docs_type", "type"),
    )


class AssetImportJob(Base):
    __tablename__ = "am_asset_import_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False)
    industry_tag = Column(String(100), nullable=False, server_default="generic")
    source_format = Column(String(20), nullable=False, server_default="csv")
    status = Column(String(40), nullable=False, server_default="CREATED")
    stage = Column(String(80), nullable=False, server_default="FILE_UPLOAD_PREVIEW")
    total_records = Column(Integer, nullable=False, server_default="0")
    parsed_records = Column(Integer, nullable=False, server_default="0")
    valid_records = Column(Integer, nullable=False, server_default="0")
    failed_records = Column(Integer, nullable=False, server_default="0")
    imported_records = Column(Integer, nullable=False, server_default="0")
    merged_dataset_id = Column(String(36), nullable=True)
    mapping_config_id = Column(String(36), nullable=True)
    parent_job_id = Column(String(36), nullable=True)
    approved_by = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    error_report = Column(JSONB, nullable=False, server_default='{"summary": {}, "errors": []}')
    mapping = Column(JSONB, nullable=True)
    import_summary = Column(JSONB, nullable=True)


class AssetImportFile(Base):
    __tablename__ = "am_asset_import_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_job_id = Column(String(36), nullable=False, index=True)
    file_name = Column(Text, nullable=False)
    file_size_kb = Column(Float, nullable=False, server_default="0")
    format = Column(String(20), nullable=False)
    status = Column(String(40), nullable=False, server_default="previewed")
    active_sheet = Column(Text, nullable=True)
    sheets = Column(JSONB, nullable=False, server_default="[]")
    rows = Column(JSONB, nullable=False, server_default="[]")
    parse_warnings = Column(ARRAY(Text), nullable=False, server_default="{}")
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AssetImportMappingConfig(Base):
    __tablename__ = "am_asset_import_mapping_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, nullable=False)
    industry_tag = Column(String(100), nullable=False, server_default="generic")
    source_format = Column(String(20), nullable=False, server_default="csv")
    is_template = Column(Boolean, nullable=False, server_default="false")
    field_mappings = Column(JSONB, nullable=False, server_default="[]")
    type_mappings = Column(JSONB, nullable=False, server_default="{}")
    hierarchy_rules = Column(JSONB, nullable=False, server_default="{}")
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
