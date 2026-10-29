"""Store a workspace AI gateway secret and encrypted agent logins.

Revision ID: 0004_workspace_agent_credentials
Revises: 0003_sp_and_nested_groups
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004_workspace_agent_credentials"
down_revision: Union[str, None] = "0003_sp_and_nested_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_gateway_secrets",
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspace_gateway_secrets_token_hash", "workspace_gateway_secrets", ["token_hash"], unique=True)

    op.create_table(
        "workspace_agent_credentials",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent", sa.String(32), nullable=False),
        sa.Column("files_enc", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "agent", name="uq_workspace_agent_credential"),
    )


def downgrade() -> None:
    op.drop_table("workspace_agent_credentials")
    op.drop_index("ix_workspace_gateway_secrets_token_hash", table_name="workspace_gateway_secrets")
    op.drop_table("workspace_gateway_secrets")
