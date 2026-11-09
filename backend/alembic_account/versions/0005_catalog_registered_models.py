"""Registered models, versions, and aliases in the data catalog.

Revision ID: 0005_catalog_registered_models
Revises: 0004_workspace_agent_credentials
Create Date: 2026-11-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_catalog_registered_models"
down_revision: Union[str, None] = "0004_workspace_agent_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_registered_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("schema_id", sa.String(36), sa.ForeignKey("catalog_v2_schemas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_name", sa.String(255), nullable=False),
        sa.Column("schema_name", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(765), sa.Computed("catalog_name || '.' || schema_name || '.' || name", persisted=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("storage_location", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.UniqueConstraint("catalog_name", "schema_name", "name", name="uq_catalog_registered_models_name"),
    )
    op.create_table(
        "catalog_model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("catalog_registered_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING_REGISTRATION"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("storage_location", sa.Text(), nullable=True),
        sa.Column("files", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("params", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("model_id", "version", name="uq_catalog_model_versions_version"),
    )
    op.create_table(
        "catalog_model_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("catalog_registered_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("model_id", "alias", name="uq_catalog_model_aliases_alias"),
    )


def downgrade() -> None:
    op.drop_table("catalog_model_aliases")
    op.drop_table("catalog_model_versions")
    op.drop_table("catalog_registered_models")
