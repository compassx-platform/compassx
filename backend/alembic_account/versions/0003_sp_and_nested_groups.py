"""Add Service Principals, Secrets, Nested Groups, and Delegated Managers.

Revision ID: 0003_sp_and_nested_groups
Revises: 0002_drop_llm_use_for_memory
Create Date: 2026-09-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003_sp_and_nested_groups"
down_revision: Union[str, None] = "0002_drop_llm_use_for_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Service Principals
    op.create_table(
        "um_service_principals",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=False), nullable=False),
        sa.Column("application_id", UUID(as_uuid=False), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "account_id",
            "application_id",
            name="uq_um_sp_account_application_id",
        ),
    )
    op.create_index(
        "ix_um_service_principals_account_id",
        "um_service_principals",
        ["account_id"],
    )

    # 2. Service Principal Secrets
    op.create_table(
        "um_service_principal_secrets",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "sp_id",
            UUID(as_uuid=False),
            sa.ForeignKey("um_service_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("secret_hash", sa.Text(), nullable=False),
        sa.Column("secret_prefix", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_um_service_principal_secrets_sp_id",
        "um_service_principal_secrets",
        ["sp_id"],
    )

    # 3. Nested Groups
    op.create_table(
        "um_group_nestings",
        sa.Column(
            "parent_group_id",
            UUID(as_uuid=False),
            sa.ForeignKey("um_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "child_group_id",
            UUID(as_uuid=False),
            sa.ForeignKey("um_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_um_group_nestings_child",
        "um_group_nestings",
        ["child_group_id"],
    )

    # 4. Group Managers (Delegated administration)
    op.create_table(
        "um_group_managers",
        sa.Column(
            "group_id",
            UUID(as_uuid=False),
            sa.ForeignKey("um_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=False),
            sa.ForeignKey("um_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 5. Service Principal ACLs (Delegated managers & users)
    op.create_table(
        "um_sp_acls",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "sp_id",
            UUID(as_uuid=False),
            sa.ForeignKey("um_service_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("principal_id", UUID(as_uuid=False), nullable=False),
        sa.Column("principal_type", sa.String(20), nullable=False),
        sa.Column("acl_role", sa.String(32), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "sp_id",
            "principal_id",
            "acl_role",
            name="uq_um_sp_acls_identity",
        ),
    )
    op.create_index("ix_um_sp_acls_sp_id", "um_sp_acls", ["sp_id"])


def downgrade() -> None:
    op.drop_table("um_sp_acls")
    op.drop_table("um_group_managers")
    op.drop_table("um_group_nestings")
    op.drop_table("um_service_principal_secrets")
    op.drop_table("um_service_principals")
