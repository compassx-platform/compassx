"""SQLAlchemy ORM model for catalog_v2_storage_backends."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import AccountBase as Base


def _uuid() -> str:
    return str(uuid4())


class StorageBackend(Base):
    __tablename__ = "catalog_v2_storage_backends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # azure | s3 | minio

    # Azure-specific
    azure_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    azure_container: Mapped[str | None] = mapped_column(String(255), nullable=True)
    azure_base_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_azure_account_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    azure_tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    azure_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_azure_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)

    # S3 / MinIO-specific
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_base_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    s3_endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_access_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_secret_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Common
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
