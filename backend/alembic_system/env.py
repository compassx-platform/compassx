"""Alembic env for the system (data / operational plane) DB: compassx_system.

Tables in this DB (SystemBase):
  Partitioned logs: wp_query_history, wp_agent_run_logs, wp_agent_turn_logs, wp_llm_call_logs
  Sessions/warehouses: wp_sessions, wp_sql_warehouses, wp_srm_memories
  Query history: query.active_queries, query.history
  Agents: agents, agent_tools, agent_db_connections, agent_git_connections,
          agent_context_entries, agent_skill_attachments, conversations, messages,
          tasks, triggers, chat_sessions, chat_messages, skills
  LLM/Budget: llm_call_logs, budgets, budget_statuses
  Research: research_engine_runs, research_proposals, research_proposal_messages
  RAG: rag_documents, rag_chunks, business_context_entries
  Dashboard: dashboards
  SQL Warehouse: sql_warehouse_warehouses
  Jobs: jobs, job_tasks, job_task_dependencies, job_runs, job_task_runs
        run_trace, run_trace_step, run_trace_step_data_sample
  User Management: users, roles, permissions, user_roles
  Jobs: jobs.jobs, jobs.job_versions, jobs.airflow_job_specs, run history
  Documents: documents, document_chunks
  Compute: compute_resources, compute_resource_deployments
  Asset Manager: asset_types, asset_instances, asset_relationships,
                 asset_events, tags_def, asset_tags, asset_import_jobs, asset_memories
  Data: datasets

Run: alembic -c alembic_system.ini upgrade head
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402

# Import ALL models that live in SystemBase (compassx_system)
from app.workspace import data_models as workspace_data_models  # noqa: F401, E402
import app.agents.models.agents  # noqa: F401, E402  (Agent, Skill, Budget, ResearchMemory, etc.)
import app.sql_warehouse.models  # noqa: F401, E402  (SqlWarehouse, SqlQueryRecord, SqlActiveQuery)
import app.dashboards.models.dashboard  # noqa: F401, E402
import app.jobs.models.job  # noqa: F401, E402
import app.jobs.models.run_trace  # noqa: F401, E402
import app.compute.models.compute_resources  # noqa: F401, E402
import app.asset_manager.models.asset_manager  # noqa: F401, E402
import app.data.models.dataset  # noqa: F401, E402

from app.database import SystemBase  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.resolved_data_db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SystemBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
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
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
