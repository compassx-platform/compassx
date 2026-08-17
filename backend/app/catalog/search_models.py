"""SQLAlchemy ORM models for catalog_search schema.

These models live in the compassx_account DB (AccountBase) alongside
the catalog_v2_* tables. They are never the source of truth for catalog
metadata — they are a denormalized, embeddable projection of it.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import AccountBase as Base

try:
    from pgvector.sqlalchemy import Vector
    _VECTOR_TYPE = Vector(1536)
except ImportError:
    from sqlalchemy import Text as _VectorTextFallback
    _VECTOR_TYPE = _VectorTextFallback()  # type: ignore[assignment]


class CatalogSearchAsset(Base):
    """One row per searchable catalog object.

    The ``embedding`` column is NULL until the async worker calls Voyage AI
    and writes the resulting vector.  Rows with NULL embeddings are excluded
    from search results.
    """

    __tablename__ = "assets"
    __table_args__ = {"schema": "vector_db"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Object identity
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_name: Mapped[str] = mapped_column(Text, nullable=False)
    schema_name: Mapped[str] = mapped_column(Text, nullable=False)
    object_name: Mapped[str] = mapped_column(Text, nullable=False)
    # UUID/string PK from the canonical catalog table (catalog_v2_tables.id etc.)
    source_object_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Embeddable metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)

    # The vector itself — NULL until embedded
    embedding: Mapped[object | None] = mapped_column(_VECTOR_TYPE, nullable=True)
    # Records which LLM connection (model name) produced this embedding
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False, default="llm-connection")

    # Foreign-object flags
    is_foreign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CatalogSearchEmbeddingJob(Base):
    """Polling job queue for asynchronous embedding generation.

    Mirrors the async job-table pattern used by the Layer 1 profiler.
    """

    __tablename__ = "embedding_jobs"
    __table_args__ = {"schema": "vector_db"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vector_db.assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    # status: pending | in_progress | completed | failed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CatalogSearchForeignSyncLog(Base):
    """Tracks user-triggered foreign catalog sync operations."""

    __tablename__ = "foreign_sync_log"
    __table_args__ = {"schema": "vector_db"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    foreign_catalog_name: Mapped[str] = mapped_column(Text, nullable=False)
    connection_id: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_by_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    # status: running | completed | failed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    tables_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
