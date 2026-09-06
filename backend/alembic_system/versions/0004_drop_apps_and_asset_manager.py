"""Drop legacy apps and asset manager tables.

Revision ID: 0004_drop_apps_and_asset_manager
Revises: 0003_governance_engine
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0004_drop_apps_and_asset_manager"
down_revision: Union[str, None] = "0003_governance_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop legacy App tables ───────────────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS app_chat_messages CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_chat_sessions CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_pods CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_production_pointer CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_credential_grants CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_branches CASCADE;")
    op.execute("DROP TABLE IF EXISTS app_commits CASCADE;")
    op.execute("DROP TABLE IF EXISTS git_config CASCADE;")
    op.execute("DROP TABLE IF EXISTS apps CASCADE;")

    # ── Drop legacy Asset Manager tables ─────────────────────────────────────
    op.execute("DROP TABLE IF EXISTS am_asset_import_mapping_configs CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_import_files CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_import_jobs CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_documents CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_tags CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_tags_def CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_relationships CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_versions CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_instances CASCADE;")
    op.execute("DROP TABLE IF EXISTS am_asset_types CASCADE;")


def downgrade() -> None:
    # Irreversible drop migration
    pass
