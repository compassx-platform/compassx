"""User Manager — system_db SQLAlchemy models.

All tables here live in compassx_system (system_db, using SystemBase).
workspace_id is a SOFT REFERENCE to account_db workspaces — no FK enforced.
"""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import SystemBase


def _uuid() -> str:
    return str(uuid4())


class UmPrincipalType(str, enum.Enum):
    user  = "user"
    group = "group"


# ─────────────────────────────────────────────────────────────────
# workspace_roles  (static reference table — seeded at setup)
# ─────────────────────────────────────────────────────────────────

class UmWorkspaceRole(SystemBase):
    __tablename__ = "um_workspace_roles"

    id:           Mapped[str]      = mapped_column(String(50), primary_key=True)  # 'workspace_admin' | 'analyst' | 'business_viewer'
    display_name: Mapped[str]      = mapped_column(String(255), nullable=False)
    description:  Mapped[str|None] = mapped_column(Text, nullable=True)

    assignments:   Mapped[list["UmWorkspaceRoleAssignment"]] = relationship(back_populates="role")
    landing_rules: Mapped[list["UmLandingRule"]] = relationship(back_populates="role")


# ─────────────────────────────────────────────────────────────────
# workspace_role_assignments
# Soft-refs: workspace_id → account_db workspaces.id
#            principal_id → account_db users.id or groups.id
# ─────────────────────────────────────────────────────────────────

class UmWorkspaceRoleAssignment(SystemBase):
    __tablename__ = "um_workspace_role_assignments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "principal_id", "principal_type",
                         name="uq_um_wra_workspace_principal"),
        Index("ix_um_wra_principal", "principal_id", "principal_type"),
    )

    id:             Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workspace_id:   Mapped[str]      = mapped_column(UUID(as_uuid=False), nullable=False, index=True)   # soft ref
    principal_id:   Mapped[str]      = mapped_column(UUID(as_uuid=False), nullable=False)               # soft ref
    principal_type: Mapped[str]      = mapped_column(
        Enum(UmPrincipalType, name="um_principal_type_sys", create_type=False),
        nullable=False,
    )
    role_id:        Mapped[str]      = mapped_column(String(50), ForeignKey("um_workspace_roles.id"), nullable=False)
    is_default:     Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False)
    granted_by:     Mapped[str|None] = mapped_column(UUID(as_uuid=False), nullable=True)               # soft ref
    granted_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    role: Mapped["UmWorkspaceRole"] = relationship(back_populates="assignments")


# ─────────────────────────────────────────────────────────────────
# landing_rules
# ─────────────────────────────────────────────────────────────────

class UmLandingRule(SystemBase):
    __tablename__ = "um_landing_rules"

    id:           Mapped[str]      = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    scope_type:   Mapped[str]      = mapped_column(String(20), nullable=False)             # 'global' | 'workspace'
    scope_id:     Mapped[str|None] = mapped_column(UUID(as_uuid=False), nullable=True)    # null if global
    role_id:      Mapped[str]      = mapped_column(String(50), ForeignKey("um_workspace_roles.id"), nullable=False)
    target_route: Mapped[str]      = mapped_column(String(500), nullable=False)
    priority:     Mapped[int]      = mapped_column(Integer, nullable=False, default=0)

    role: Mapped["UmWorkspaceRole"] = relationship(back_populates="landing_rules")


# ─────────────────────────────────────────────────────────────────
# object_grants
#
# The um_object_grants table is now declared and enforced by the governance
# engine: see app/governance/models.py (ObjectGrant). The declaration was moved
# there because the governance package owns the columns that make it
# evaluable — securable_type, privilege, expires_at — and two mapped classes
# for one table would conflict.
# ─────────────────────────────────────────────────────────────────
