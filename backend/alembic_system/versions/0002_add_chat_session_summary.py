"""Add summary and summary_updated_at columns to ai.chat_sessions.

Revision ID: 0002_add_chat_session_summary
Revises: 0001_initial_system_schema
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_chat_session_summary"
down_revision: Union[str, None] = "0001_initial_system_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE ai.chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT;")
    op.execute("ALTER TABLE ai.chat_sessions ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMPTZ;")


def downgrade() -> None:
    op.execute("ALTER TABLE ai.chat_sessions DROP COLUMN IF EXISTS summary_updated_at;")
    op.execute("ALTER TABLE ai.chat_sessions DROP COLUMN IF EXISTS summary;")
