'''Create apps.app_tasks table for application task tracking.

Revision ID: 0007_app_tasks
Revises: 0006_dev_workspaces
Create Date: 2026-09-11
'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_app_tasks"
down_revision: Union[str, None] = "0006_dev_workspaces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_tasks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="backlog"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("tags", sa.JSON().with_variant(JSONB, "postgresql"), nullable=True),
        sa.Column("assignee", sa.String(length=128), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema="apps",
    )
    op.create_index("ix_apps_app_tasks_app_id", "app_tasks", ["app_id"], schema="apps")
    op.create_index("ix_apps_app_tasks_workspace_id", "app_tasks", ["workspace_id"], schema="apps")
    op.create_index("ix_apps_app_tasks_status", "app_tasks", ["status"], schema="apps")


def downgrade() -> None:
    op.drop_index("ix_apps_app_tasks_status", table_name="app_tasks", schema="apps")
    op.drop_index("ix_apps_app_tasks_workspace_id", table_name="app_tasks", schema="apps")
    op.drop_index("ix_apps_app_tasks_app_id", table_name="app_tasks", schema="apps")
    op.drop_table("app_tasks", schema="apps")
