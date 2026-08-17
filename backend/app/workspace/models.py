"""Control plane models for compassx_account database.

All tables here live in the system (control plane) DB.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AccountBase


def _uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# accounts
# One row per CompassX deployment.
# ---------------------------------------------------------------------------
class Account(AccountBase):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    principals: Mapped[list["Principal"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    catalogs: Mapped[list["WorkspaceCatalog"]] = relationship(back_populates="account", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# principals
# Unified identity table: users, groups, service principals.
# ---------------------------------------------------------------------------
class Principal(AccountBase):
    __tablename__ = "principals"
    __table_args__ = (
        UniqueConstraint("account_id", "email", name="uq_principals_account_email"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        # CHECK enforced at DB level via migration
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_account_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idp_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    idp_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account: Mapped[Account] = relationship(back_populates="principals")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        back_populates="principal",
        foreign_keys="WorkspaceMembership.principal_id",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# workspaces
# ---------------------------------------------------------------------------
class Workspace(AccountBase):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    storage_backend: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("principals.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account: Mapped[Account] = relationship(back_populates="workspaces")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# workspace_memberships
# ---------------------------------------------------------------------------
class WorkspaceMembership(AccountBase):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "principal_id", name="uq_membership_workspace_principal"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("principals.id"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
    principal: Mapped[Principal] = relationship(back_populates="memberships", foreign_keys=[principal_id])


# ---------------------------------------------------------------------------
# catalogs  (account-level, shared across workspaces)
# ---------------------------------------------------------------------------
class WorkspaceCatalog(AccountBase):
    __tablename__ = "workspace_catalogs"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_workspace_catalog_account_name"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("accounts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_root: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    connection_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    connection_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account: Mapped[Account] = relationship(back_populates="catalogs")
    schemas: Mapped[list["WorkspaceCatalogSchema"]] = relationship(back_populates="catalog", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# schemas  (within a catalog)
# ---------------------------------------------------------------------------
class WorkspaceCatalogSchema(AccountBase):
    __tablename__ = "workspace_catalog_schemas"
    __table_args__ = (
        UniqueConstraint("catalog_id", "name", name="uq_workspace_catalog_schema_name"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    catalog_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("workspace_catalogs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    blob_prefix: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    catalog: Mapped[WorkspaceCatalog] = relationship(back_populates="schemas")
    objects: Mapped[list["CatalogObject"]] = relationship(back_populates="schema", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# catalog_objects
# ---------------------------------------------------------------------------
class CatalogObject(AccountBase):
    __tablename__ = "workspace_catalog_objects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    schema_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("workspace_catalog_schemas.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    object_type: Mapped[str] = mapped_column(String(30), nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="workspace")
    home_workspace_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("workspaces.id"), nullable=True)
    blob_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    owner_principal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("principals.id"), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    schema: Mapped[WorkspaceCatalogSchema] = relationship(back_populates="objects")


# ---------------------------------------------------------------------------
# permissions  (securable access grants)
# ---------------------------------------------------------------------------
class CatalogPermission(AccountBase):
    __tablename__ = "workspace_catalog_permissions"
    __table_args__ = (
        UniqueConstraint("securable_type", "securable_id", "principal_id", "privilege", name="uq_catalog_permission"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    securable_type: Mapped[str] = mapped_column(String(20), nullable=False)
    securable_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False)
    privilege: Mapped[str] = mapped_column(String(20), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("principals.id"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
