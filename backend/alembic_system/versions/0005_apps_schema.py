'''Create apps schema and apps table in system database.

Revision ID: 0005_apps_schema
Revises: 0004_drop_apps_and_asset_manager
Create Date: 2026-09-06
'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_apps_schema"
down_revision: Union[str, None] = "0004_drop_apps_and_asset_manager"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create 'apps' schema in system database ───────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS apps;")

    # ── 2. Create 'apps.apps' table ──────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS apps.apps CASCADE;")
    op.create_table(
        "apps",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_slug", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("app_type", sa.String(length=64), nullable=False, server_default="streamlit"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("route", sa.String(length=255), nullable=False),

        # Git repository and configuration
        sa.Column("git_provider", sa.String(length=64), nullable=False, server_default="github"),
        sa.Column("git_repo_url", sa.String(length=512), nullable=False),
        sa.Column("git_ref", sa.String(length=128), nullable=False, server_default="main"),
        sa.Column("git_ref_type", sa.String(length=32), nullable=False, server_default="branch"),
        sa.Column("git_branch", sa.String(length=128), nullable=False, server_default="main"),
        sa.Column("git_subdir", sa.String(length=255), nullable=True),
        sa.Column("entrypoint", sa.String(length=255), nullable=True),

        # Git credentials
        sa.Column("git_credential_type", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("git_credential_nickname", sa.String(length=255), nullable=True),
        sa.Column("git_connection_id", sa.Integer(), nullable=True),
        sa.Column("git_pat_enc", sa.Text(), nullable=True),

        # Workload Identity & Runtime Configuration
        sa.Column("workspace_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        sa.Column("created_by_user_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        schema="apps",
    )

    # Indexes for efficient workspace-scoped queries
    op.create_index("ix_apps_apps_workspace_id", "apps", ["workspace_id"], schema="apps")
    op.create_index("ix_apps_apps_workspace_slug", "apps", ["workspace_slug"], schema="apps")
    op.create_index("ix_apps_apps_slug", "apps", ["slug"], schema="apps")


def downgrade() -> None:
    op.drop_index("ix_apps_apps_slug", table_name="apps", schema="apps")
    op.drop_index("ix_apps_apps_workspace_slug", table_name="apps", schema="apps")
    op.drop_index("ix_apps_apps_workspace_id", table_name="apps", schema="apps")
    op.drop_table("apps", schema="apps")
    op.execute("DROP SCHEMA IF EXISTS apps CASCADE;")
