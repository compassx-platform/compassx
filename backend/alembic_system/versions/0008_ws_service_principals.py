"""Add service_principal to um_principal_type_sys enum for workspace assignment.

Revision ID: 0008_ws_service_principals
Revises: 0007_app_tasks
Create Date: 2026-09-20
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0008_ws_service_principals"
down_revision: Union[str, None] = "0007_app_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Check if dialect is PostgreSQL and add enum value
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TYPE um_principal_type_sys ADD VALUE IF NOT EXISTS 'service_principal';")


def downgrade() -> None:
    pass
