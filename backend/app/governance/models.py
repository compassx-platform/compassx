"""Governance persistence models.

Extends the previously dormant ``um_object_grants`` table (declared in
app/user_manager/models/system_models.py and never read by any query) into the
grant store this engine evaluates.

Changes relative to the original declaration:
  * ``securable_type`` — the original encoded object kind implicitly, by which
    of catalog/schema/asset were null. That cannot express jobs, agents,
    compute or connections, and cannot distinguish a table from a notebook of
    the same name in the same schema.
  * ``privilege`` — allows a direct privilege grant without first inventing a
    named bundle. ``object_role_id`` remains supported for bundle grants.
  * ``expires_at`` — time-bound grants, needed for agent principals.

The table lives in system_db. principal_id and workspace_id are soft
references into account_db, consistent with the surrounding user_manager
tables (there is no cross-database FK).
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import SystemBase


def _uuid() -> str:
    return str(uuid4())


class ObjectGrant(SystemBase):
    """A single grant of one privilege on one securable to one principal."""

    __tablename__ = "um_object_grants"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "principal_id",
            "securable_type",
            "catalog_name",
            "schema_name",
            "asset_name",
            "privilege",
            name="uq_um_object_grants_identity",
        ),
        # Primary lookup: load every grant held by a principal in a workspace
        # in one query, then evaluate objects in memory. See resolver.
        Index("ix_um_object_grants_principal", "workspace_id", "principal_id"),
        # Reverse lookup: "who has access to this object?" for the UI.
        Index(
            "ix_um_object_grants_securable",
            "workspace_id",
            "catalog_name",
            "schema_name",
            "asset_name",
        ),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)

    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    #: User, group, or service (agent) principal. Soft ref into account_db.
    principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(20), nullable=False)

    #: SecurableType value. Required — see module docstring.
    securable_type: Mapped[str] = mapped_column(String(32), nullable=False)

    #: Catalog path. For workspace-scoped securables catalog_name holds the
    #: WORKSPACE_SENTINEL and asset_name holds the object id.
    catalog_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    #: Exactly one of privilege / object_role_id is set.
    privilege: Mapped[str | None] = mapped_column(String(32), nullable=True)
    object_role_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    granted_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: Null means the grant does not expire. Used for time-bound agent grants.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SecurableOwner(SystemBase):
    """Ownership of a governed object.

    Ownership is stored centrally rather than as an ``owner`` column on each of
    the twelve securable tables. That keeps ownership lookup uniform for the
    resolver and means adding a new securable type requires no schema change.

    The owner may be a user or a group. Group ownership is deliberate: it stops
    assets being orphaned when an employee leaves, which is a recurring
    operational problem in platforms that only allow user ownership.
    """

    __tablename__ = "um_securable_owners"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "securable_type",
            "catalog_name",
            "schema_name",
            "asset_name",
            name="uq_um_securable_owners_identity",
        ),
        Index("ix_um_securable_owners_principal", "workspace_id", "owner_principal_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)

    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    securable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    catalog_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    owner_principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    owner_principal_type: Mapped[str] = mapped_column(String(20), nullable=False)

    assigned_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentPrincipal(SystemBase):
    """Service identity for an agent.

    Agents hold their own grants (owner decision, 2026-08-29). The containment
    rule is that an agent's effective privileges are intersected with its
    owner's at evaluation time, so an agent can never exceed the person
    responsible for it, and loses access the moment its owner does.

    ``owner_principal_id`` is therefore load-bearing for security, not just
    provenance.
    """

    __tablename__ = "um_agent_principals"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_um_agent_principals_agent"),
        Index("ix_um_agent_principals_principal", "principal_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)

    #: The agent this identity belongs to.
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The principal id used in grants. principal_type is always 'service'.
    principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, default=_uuid)

    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    #: Ceiling for the agent's effective privileges.
    owner_principal_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    owner_principal_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccessAuditLog(SystemBase):
    """Audit trail for authorization decisions and grant administration.

    Denials are recorded alongside allows: an access-review process needs to
    see attempted access, not only successful access.

    ``on_behalf_of_principal_id`` carries the invoking user when an agent
    service identity performs the access, so attribution is never lost at the
    point it matters most.
    """

    __tablename__ = "um_access_audit_log"
    __table_args__ = (
        Index("ix_um_access_audit_ws_time", "workspace_id", "created_at"),
        Index("ix_um_access_audit_principal", "principal_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)

    workspace_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)

    #: 'access' for authorization decisions; 'grant' / 'revoke' /
    #: 'transfer_ownership' for administration.
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)

    principal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    principal_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: Set when an agent acted for a user. See AgentPrincipal.
    on_behalf_of_principal_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)

    securable_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    securable_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    privilege: Mapped[str | None] = mapped_column(String(32), nullable=True)

    #: 'allow' | 'deny' for access events; null for administration events.
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: Why the decision was reached — owner, direct grant, inherited, etc.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
