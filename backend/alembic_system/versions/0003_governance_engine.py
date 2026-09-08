"""Governance engine: grants, ownership, agent identities, access audit.

Revision ID: 0003_governance_engine
Revises: 0002_add_chat_session_summary
Create Date: 2026-08-29

``um_object_grants`` already existed but was never read by any query — it had
no ``securable_type``, so it could not express jobs, agents, compute or
connections, and could not tell a table from a notebook of the same name in
the same schema. It is dropped and recreated rather than altered: the old
rows have no securable_type to infer and would evaluate as something other
than what their author intended, which is worse than having no grant at all.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003_governance_engine"
down_revision: Union[str, None] = "0002_add_chat_session_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS um_access_audit_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS um_agent_principals CASCADE;")
    op.execute("DROP TABLE IF EXISTS um_securable_owners CASCADE;")
    op.execute("DROP TABLE IF EXISTS um_object_grants CASCADE;")

    op.create_table(
        "um_object_grants",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=False), nullable=False),
        sa.Column("principal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("principal_type", sa.String(20), nullable=False),
        sa.Column("securable_type", sa.String(32), nullable=False),
        sa.Column("catalog_name", sa.String(255), nullable=False),
        sa.Column("schema_name", sa.String(255), nullable=True),
        sa.Column("asset_name", sa.String(255), nullable=True),
        sa.Column("privilege", sa.String(32), nullable=True),
        sa.Column("object_role_id", sa.String(100), nullable=True),
        sa.Column("granted_by", UUID(as_uuid=False), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "principal_id",
            "securable_type",
            "catalog_name",
            "schema_name",
            "asset_name",
            "privilege",
            name="uq_um_object_grants_identity",
        ),
    )
    op.create_index("ix_um_object_grants_workspace_id", "um_object_grants", ["workspace_id"])
    # Primary lookup: every grant held by a principal, in one query. This index
    # is what keeps a list endpoint to a constant number of queries.
    op.create_index(
        "ix_um_object_grants_principal", "um_object_grants", ["workspace_id", "principal_id"]
    )
    # Reverse lookup for the Permissions tab: who can reach this object?
    op.create_index(
        "ix_um_object_grants_securable",
        "um_object_grants",
        ["workspace_id", "catalog_name", "schema_name", "asset_name"],
    )

    op.create_table(
        "um_securable_owners",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=False), nullable=False),
        sa.Column("securable_type", sa.String(32), nullable=False),
        sa.Column("catalog_name", sa.String(255), nullable=False),
        sa.Column("schema_name", sa.String(255), nullable=True),
        sa.Column("asset_name", sa.String(255), nullable=True),
        sa.Column("owner_principal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("owner_principal_type", sa.String(20), nullable=False),
        sa.Column("assigned_by", UUID(as_uuid=False), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "securable_type",
            "catalog_name",
            "schema_name",
            "asset_name",
            name="uq_um_securable_owners_identity",
        ),
    )
    op.create_index(
        "ix_um_securable_owners_workspace_id", "um_securable_owners", ["workspace_id"]
    )
    # "What does this person own?" — asked on every offboarding.
    op.create_index(
        "ix_um_securable_owners_principal",
        "um_securable_owners",
        ["workspace_id", "owner_principal_id"],
    )

    op.create_table(
        "um_agent_principals",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("principal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=False), nullable=False),
        # Ceiling for the agent's effective privileges — security-relevant,
        # not provenance. See app/governance/resolver.py.
        sa.Column("owner_principal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("owner_principal_type", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("agent_id", name="uq_um_agent_principals_agent"),
    )
    op.create_index(
        "ix_um_agent_principals_workspace_id", "um_agent_principals", ["workspace_id"]
    )
    op.create_index(
        "ix_um_agent_principals_principal", "um_agent_principals", ["principal_id"]
    )

    op.create_table(
        "um_access_audit_log",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=False), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("principal_id", UUID(as_uuid=False), nullable=True),
        sa.Column("principal_type", sa.String(20), nullable=True),
        # Set when an agent acted for a user, so attribution survives.
        sa.Column("on_behalf_of_principal_id", UUID(as_uuid=False), nullable=True),
        sa.Column("securable_type", sa.String(32), nullable=True),
        sa.Column("securable_name", sa.Text(), nullable=True),
        sa.Column("privilege", sa.String(32), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_um_access_audit_log_workspace_id", "um_access_audit_log", ["workspace_id"]
    )
    op.create_index(
        "ix_um_access_audit_ws_time", "um_access_audit_log", ["workspace_id", "created_at"]
    )
    op.create_index(
        "ix_um_access_audit_principal", "um_access_audit_log", ["principal_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("um_access_audit_log")
    op.drop_table("um_agent_principals")
    op.drop_table("um_securable_owners")
    op.drop_table("um_object_grants")
