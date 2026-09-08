"""Drop the obsolete LLM memory-provider flag.

Revision ID: 0002_drop_llm_use_for_memory
Revises: 0001_initial_account_schema
Create Date: 2026-08-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_drop_llm_use_for_memory"
down_revision: Union[str, None] = "0001_initial_account_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE llm_connections DROP COLUMN IF EXISTS use_for_memory")


def downgrade() -> None:
    op.add_column(
        "llm_connections",
        sa.Column(
            "use_for_memory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
