"""Alembic env for the account (control plane) DB: compassx_account.

Tables in this DB (AccountBase):
  - accounts, principals, workspaces, workspace_memberships
  - workspace_catalogs, workspace_catalog_schemas, workspace_catalog_objects, workspace_catalog_permissions
  - llm_connections, db_connections, git_connections
  - catalog_v2_catalogs, catalog_v2_schemas, catalog_v2_tables, catalog_v2_columns
  - catalog_v2_volumes, catalog_v2_volume_files, catalog_v2_lineage, catalog_notebooks
  - catalog_v2_storage_backends
  - catalog_connections
  - data_source_profiles

Run: alembic -c alembic_account.ini upgrade head
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402

# Import ALL models that live in AccountBase (compassx_account)
from app.workspace import models as workspace_models  # noqa: F401, E402
from app.catalog import models as catalog_models  # noqa: F401, E402
from app.catalog import search_models as catalog_search_models  # noqa: F401, E402
from app.dashboards.models import dashboard as dashboard_models  # noqa: F401, E402
from app.storage import db_models as storage_models  # noqa: F401, E402
from app.data.models import data_catalog as legacy_catalog_models  # noqa: F401, E402
import app.agents.models.agents  # noqa: F401, E402  (LLMConnection, DBConnection, GitConnection)

from app.database import AccountBase  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.resolved_system_db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = AccountBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
