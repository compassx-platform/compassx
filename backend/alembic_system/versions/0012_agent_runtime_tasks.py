"""Add agent runtime tasks.

Revision ID: 0012_agent_runtime_tasks
Revises: 0011_agent_runtime_projects
Create Date: 2026-11-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012_agent_runtime_tasks"
down_revision: Union[str, None] = "0011_agent_runtime_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()
    if "agent_runtime_tasks" in tables:
        return
    op.create_table(
        "agent_runtime_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("waiting_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_session_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("agent_type", sa.String(length=64), nullable=False, server_default="nova"),
        sa.Column("llm_model", sa.String(length=255), nullable=True),
        sa.Column("events", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agent_runtime_tasks_workspace_id", "agent_runtime_tasks", ["workspace_id"])
    op.create_index("ix_agent_runtime_tasks_project_id", "agent_runtime_tasks", ["project_id"])
    op.create_index("ix_agent_runtime_tasks_stage", "agent_runtime_tasks", ["stage"])
    op.create_index("ix_agent_runtime_tasks_session_id", "agent_runtime_tasks", ["session_id"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "agent_runtime_tasks" not in insp.get_table_names():
        return
    op.drop_index("ix_agent_runtime_tasks_session_id", table_name="agent_runtime_tasks")
    op.drop_index("ix_agent_runtime_tasks_stage", table_name="agent_runtime_tasks")
    op.drop_index("ix_agent_runtime_tasks_project_id", table_name="agent_runtime_tasks")
    op.drop_index("ix_agent_runtime_tasks_workspace_id", table_name="agent_runtime_tasks")
    op.drop_table("agent_runtime_tasks")
