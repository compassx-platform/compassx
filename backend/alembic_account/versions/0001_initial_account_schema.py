"""Initial consolidated schema for compassx_account (Control Plane).

Revision ID: 0001_initial_account_schema
Revises: (none — baseline migration)
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op

from app.database import AccountBase
import app.workspace.models  # noqa: F401
import app.catalog.models  # noqa: F401
import app.catalog.search_models  # noqa: F401
import app.dashboards.models.dashboard  # noqa: F401
import app.storage.db_models  # noqa: F401
import app.agents.models.agents  # noqa: F401

revision: str = "0001_initial_account_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"vector\";")
    op.execute("CREATE SCHEMA IF NOT EXISTS vector_db;")

    AccountBase.metadata.create_all(bind=conn)


def downgrade() -> None:
    conn = op.get_bind()
    AccountBase.metadata.drop_all(bind=conn)
