"""Initial consolidated schema for compassx_system (Data / Operational Plane).

Revision ID: 0001_initial_system_schema
Revises: (none — baseline migration)
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op

from app.database import SystemBase
import app.workspace.data_models  # noqa: F401
import app.agents.models.agents  # noqa: F401
import app.sql_warehouse.models  # noqa: F401
import app.dashboards.models.dashboard  # noqa: F401
import app.jobs.models.job  # noqa: F401
import app.jobs.models.run_trace  # noqa: F401
import app.workflows.models.entity  # noqa: F401
import app.workflows.models.workflow  # noqa: F401
import app.workflows.models.audit  # noqa: F401
import app.compute.models.compute_resources  # noqa: F401
import app.asset_manager.models.asset_manager  # noqa: F401
import app.data.models.dataset  # noqa: F401
import app.apps.models.apps  # noqa: F401
import app.apps.models.app_chat  # noqa: F401

revision: str = "0001_initial_system_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"vector\";")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai;")
    op.execute("CREATE SCHEMA IF NOT EXISTS jobs;")
    op.execute("CREATE SCHEMA IF NOT EXISTS compute;")
    op.execute("CREATE SCHEMA IF NOT EXISTS query;")

    SystemBase.metadata.create_all(bind=conn)


def downgrade() -> None:
    conn = op.get_bind()
    SystemBase.metadata.drop_all(bind=conn)
