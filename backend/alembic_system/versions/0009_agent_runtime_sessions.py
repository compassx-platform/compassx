"""Create agent_runtime_sessions table for multi-replica persistent agent sessions.

Revision ID: 0009_agent_runtime_sessions
Revises: 0008_ws_service_principals
Create Date: 2026-10-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_agent_runtime_sessions"
down_revision: Union[str, None] = "0008_ws_service_principals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"
    json_type = postgresql.JSONB(astext_type=sa.Text()) if is_pg else sa.JSON()

    op.create_table(
        "agent_runtime_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Agent Session"),
        sa.Column("agent_type", sa.String(length=64), nullable=False, server_default="antigravity"),
        sa.Column("sandbox_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("messages", json_type, nullable=False, server_default=sa.text("'[]'")),
    )
    op.create_index("ix_agent_runtime_sessions_workspace_id", "agent_runtime_sessions", ["workspace_id"])
    op.create_index("ix_agent_runtime_sessions_sandbox_id", "agent_runtime_sessions", ["sandbox_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_runtime_sessions_sandbox_id", table_name="agent_runtime_sessions")
    op.drop_index("ix_agent_runtime_sessions_workspace_id", table_name="agent_runtime_sessions")
    op.drop_table("agent_runtime_sessions")
