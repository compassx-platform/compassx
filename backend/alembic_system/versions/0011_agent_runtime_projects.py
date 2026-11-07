"""Add agent runtime projects and session project_id.

Revision ID: 0011_agent_runtime_projects
Revises: 0010_sql_warehouse_container_support
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_agent_runtime_projects"
down_revision: Union[str, None] = "0010_sql_warehouse_container_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    if "agent_runtime_projects" not in tables:
        op.create_table(
            "agent_runtime_projects",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("workspace_id", sa.String(length=64), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_agent_runtime_projects_workspace_id", "agent_runtime_projects", ["workspace_id"])

    if "agent_runtime_sessions" in tables:
        columns = [column["name"] for column in insp.get_columns("agent_runtime_sessions")]
        if "project_id" not in columns:
            op.add_column("agent_runtime_sessions", sa.Column("project_id", sa.String(length=64), nullable=True))
        indexes = [index["name"] for index in insp.get_indexes("agent_runtime_sessions")]
        if "ix_agent_runtime_sessions_project_id" not in indexes:
            op.create_index("ix_agent_runtime_sessions_project_id", "agent_runtime_sessions", ["project_id"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    if "agent_runtime_sessions" in tables:
        indexes = [index["name"] for index in insp.get_indexes("agent_runtime_sessions")]
        if "ix_agent_runtime_sessions_project_id" in indexes:
            op.drop_index("ix_agent_runtime_sessions_project_id", table_name="agent_runtime_sessions")
        columns = [column["name"] for column in insp.get_columns("agent_runtime_sessions")]
        if "project_id" in columns:
            op.drop_column("agent_runtime_sessions", "project_id")

    if "agent_runtime_projects" in tables:
        indexes = [index["name"] for index in insp.get_indexes("agent_runtime_projects")]
        if "ix_agent_runtime_projects_workspace_id" in indexes:
            op.drop_index("ix_agent_runtime_projects_workspace_id", table_name="agent_runtime_projects")
        op.drop_table("agent_runtime_projects")
