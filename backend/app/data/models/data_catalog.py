"""SQLAlchemy model for Data Catalog connection registry."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import AccountBase as Base


class CatalogConnection(Base):
    """Stores saved PostgreSQL connection credentials for the Data Catalog."""

    __tablename__ = "catalog_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=5432)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    # Password stored as Fernet-encrypted ciphertext
    password_enc: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_database: Mapped[str] = mapped_column(String(255), nullable=False, default="postgres")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )