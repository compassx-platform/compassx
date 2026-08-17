"""User Manager — account_db SQLAlchemy models.

All tables here live in compassx_account (account_db, using AccountBase).
These are additive — they coexist with the legacy workspace/models.py tables.
"""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import AccountBase


def _uuid() -> str:
    return str(uuid4())


# ─────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────

class UserStatus(str, enum.Enum):
    invited     = "invited"
    active      = "active"
    suspended   = "suspended"
    deactivated = "deactivated"


class AuthProvider(str, enum.Enum):
    local = "local"
    sso   = "sso"


class PrincipalType(str, enum.Enum):
    user  = "user"
    group = "group"


class InviteTargetScope(str, enum.Enum):
    account   = "account"
    workspace = "workspace"


class InviteStatus(str, enum.Enum):
    pending  = "pending"
    accepted = "accepted"
    expired  = "expired"
    revoked  = "revoked"


# ─────────────────────────────────────────────────────────────────
# users
# ─────────────────────────────────────────────────────────────────

class UmUser(AccountBase):
    """Authenticated identities — account_db.users."""
    __tablename__ = "um_users"
    __table_args__ = (
        UniqueConstraint("account_id", "email", name="uq_um_users_account_email"),
    )

    id:            Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id:    Mapped[str]      = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    email:         Mapped[str]      = mapped_column(String(255), nullable=False)
    display_name:  Mapped[str|None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str|None] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[str]      = mapped_column(
        Enum(AuthProvider, name="um_auth_provider", create_type=False),
        nullable=False, default=AuthProvider.local,
    )
    status:        Mapped[str]      = mapped_column(
        Enum(UserStatus, name="um_user_status", create_type=False),
        nullable=False, default=UserStatus.invited,
    )
    last_login_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    refresh_tokens: Mapped[list["UmRefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    group_memberships: Mapped[list["UmGroupMember"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    account_role_assignments: Mapped[list["UmAccountRoleAssignment"]] = relationship(
        back_populates="principal_user",
        primaryjoin="and_(UmAccountRoleAssignment.principal_id == UmUser.id, UmAccountRoleAssignment.principal_type == 'user')",
        foreign_keys="UmAccountRoleAssignment.principal_id",
        viewonly=True,
    )


# ─────────────────────────────────────────────────────────────────
# refresh_tokens
# ─────────────────────────────────────────────────────────────────

class UmRefreshToken(AccountBase):
    __tablename__ = "um_refresh_tokens"

    id:         Mapped[str]          = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id:    Mapped[str]          = mapped_column(UUID(as_uuid=False), ForeignKey("um_users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str]          = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime]     = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime]     = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime|None]= mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["UmUser"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_um_refresh_tokens_user_id", "user_id"),
    )


# ─────────────────────────────────────────────────────────────────
# groups
# ─────────────────────────────────────────────────────────────────

class UmGroup(AccountBase):
    __tablename__ = "um_groups"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_um_groups_account_name"),
    )

    id:         Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id: Mapped[str]      = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    name:       Mapped[str]      = mapped_column(String(255), nullable=False)
    source:     Mapped[str]      = mapped_column(String(20), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members: Mapped[list["UmGroupMember"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class UmGroupMember(AccountBase):
    __tablename__ = "um_group_members"

    group_id: Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("um_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id:  Mapped[str]      = mapped_column(UUID(as_uuid=False), ForeignKey("um_users.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group: Mapped["UmGroup"] = relationship(back_populates="members")
    user:  Mapped["UmUser"]  = relationship(back_populates="group_memberships")


# ─────────────────────────────────────────────────────────────────
# account_roles  (static reference table)
# ─────────────────────────────────────────────────────────────────

class UmAccountRole(AccountBase):
    __tablename__ = "um_account_roles"

    id:           Mapped[str]      = mapped_column(String(50), primary_key=True)   # 'account_admin' | 'billing_admin' | 'account_viewer'
    display_name: Mapped[str]      = mapped_column(String(255), nullable=False)
    description:  Mapped[str|None] = mapped_column(Text, nullable=True)


class UmAccountRoleAssignment(AccountBase):
    __tablename__ = "um_account_role_assignments"
    __table_args__ = (
        UniqueConstraint("account_id", "principal_id", "principal_type", "role_id",
                         name="uq_um_ara_account_principal_role"),
    )

    id:             Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id:     Mapped[str]      = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    principal_id:   Mapped[str]      = mapped_column(UUID(as_uuid=False), nullable=False)
    principal_type: Mapped[str]      = mapped_column(
        Enum(PrincipalType, name="um_principal_type", create_type=False),
        nullable=False,
    )
    role_id:        Mapped[str]      = mapped_column(String(50), ForeignKey("um_account_roles.id"), nullable=False)
    granted_by:     Mapped[str|None] = mapped_column(UUID(as_uuid=False), nullable=True)
    granted_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    role: Mapped["UmAccountRole"] = relationship()
    principal_user: Mapped["UmUser|None"] = relationship(
        "UmUser",
        primaryjoin="and_(UmAccountRoleAssignment.principal_id == UmUser.id, UmAccountRoleAssignment.principal_type == 'user')",
        foreign_keys=[principal_id],
        viewonly=True,
    )


# ─────────────────────────────────────────────────────────────────
# invites
# ─────────────────────────────────────────────────────────────────

class UmInvite(AccountBase):
    __tablename__ = "um_invites"

    id:                        Mapped[str]           = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id:                Mapped[str]           = mapped_column(UUID(as_uuid=False), nullable=False)
    email:                     Mapped[str]           = mapped_column(String(255), nullable=False, index=True)
    token_hash:                Mapped[str]           = mapped_column(Text, nullable=False, unique=True)
    target_scope:              Mapped[str]           = mapped_column(
        Enum(InviteTargetScope, name="um_invite_target_scope", create_type=False),
        nullable=False,
    )
    target_workspace_id:       Mapped[str|None]      = mapped_column(UUID(as_uuid=False), nullable=True)   # soft ref → system_db workspaces
    proposed_account_role_id:  Mapped[str|None]      = mapped_column(String(50), ForeignKey("um_account_roles.id"), nullable=True)
    proposed_workspace_role_id:Mapped[str|None]      = mapped_column(String(50), nullable=True)   # soft ref → workspace_roles
    invited_by:                Mapped[str]           = mapped_column(UUID(as_uuid=False), ForeignKey("um_users.id"), nullable=False)
    status:                    Mapped[str]           = mapped_column(
        Enum(InviteStatus, name="um_invite_status", create_type=False),
        nullable=False, default=InviteStatus.pending,
    )
    expires_at:                Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False)
    created_at:                Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    accepted_at:               Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

    inviter: Mapped["UmUser"] = relationship("UmUser", foreign_keys=[invited_by])


# ─────────────────────────────────────────────────────────────────
# user_admin_audit_log
# ─────────────────────────────────────────────────────────────────

class UmAuditLog(AccountBase):
    __tablename__ = "um_audit_log"

    id:            Mapped[str]           = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    account_id:    Mapped[str]           = mapped_column(UUID(as_uuid=False), nullable=False)
    actor_user_id: Mapped[str|None]      = mapped_column(UUID(as_uuid=False), nullable=True)
    action:        Mapped[str]           = mapped_column(String(100), nullable=False)
    target_type:   Mapped[str]           = mapped_column(String(50), nullable=False)
    target_id:     Mapped[str|None]      = mapped_column(UUID(as_uuid=False), nullable=True)
    workspace_id:  Mapped[str|None]      = mapped_column(UUID(as_uuid=False), nullable=True)   # soft ref, filter-only
    metadata_:     Mapped[dict|None]     = mapped_column("metadata", JSONB, nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_um_audit_log_account_created", "account_id", "created_at"),
    )


# ─────────────────────────────────────────────────────────────────
# permissions + object_roles + object_role_permissions
# ─────────────────────────────────────────────────────────────────

class UmPermission(AccountBase):
    __tablename__ = "um_permissions"

    id:            Mapped[str] = mapped_column(String(100), primary_key=True)   # 'notebook.read', ...
    display_name:  Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)


class UmObjectRole(AccountBase):
    __tablename__ = "um_object_roles"

    id:            Mapped[str] = mapped_column(String(100), primary_key=True)   # 'notebook_viewer', ...
    display_name:  Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)

    permissions: Mapped[list["UmObjectRolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class UmObjectRolePermission(AccountBase):
    __tablename__ = "um_object_role_permissions"

    object_role_id: Mapped[str] = mapped_column(String(100), ForeignKey("um_object_roles.id"), primary_key=True)
    permission_id:  Mapped[str] = mapped_column(String(100), ForeignKey("um_permissions.id"), primary_key=True)

    role:       Mapped["UmObjectRole"]  = relationship(back_populates="permissions")
    permission: Mapped["UmPermission"]  = relationship()
