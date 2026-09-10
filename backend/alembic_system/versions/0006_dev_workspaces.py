'''Create apps.dev_workspaces table for shared PVC workspace tracking.

Revision ID: 0006_dev_workspaces
Revises: 0005_apps_schema
Create Date: 2026-09-09
'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_dev_workspaces"
down_revision: Union[str, None] = "0005_apps_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dev_workspaces",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("folder_path", sa.String(length=512), nullable=False),
        sa.Column("git_branch", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="stopped"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        schema="apps",
    )
    op.create_index("ix_apps_dev_workspaces_app_id", "dev_workspaces", ["app_id"], schema="apps")
    op.create_index("ix_apps_dev_workspaces_workspace_id", "dev_workspaces", ["workspace_id"], schema="apps")


def downgrade() -> None:
    op.drop_index("ix_apps_dev_workspaces_workspace_id", table_name="dev_workspaces", schema="apps")
    op.drop_index("ix_apps_dev_workspaces_app_id", table_name="dev_workspaces", schema="apps")
    op.drop_table("dev_workspaces", schema="apps")
