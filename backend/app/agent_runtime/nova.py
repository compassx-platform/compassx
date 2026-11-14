"""Seed and run CompassX Nova inside an Agent Runtime sandbox session."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, selectinload

from app.models.agents import Agent, AgentTool, AgentVisibility, ChatSession

logger = logging.getLogger(__name__)

NOVA_NAME = "Nova"
NOVA_COLOR = "#4f46e5"
NOVA_TOOLS = (
    "sql_warehouse",
    "python_code",
    "visualization",
    "rag_search",
    "notebook_manager",
    "dashboard_manager",
    "catalog",
    "search_assets",
    "catalog_editor",
    "mlflow",
    "invoke_agent",
)


def runtime_chat_title(runtime_session_id: str) -> str:
    return f"runtime:{runtime_session_id}"


def ensure_nova_agent(db: Session, workspace_id: str | None) -> Agent:
    from app.agent_runtime.seeding.ensure_nova_agent import ensure_nova_agent as _action
    return _action(db, workspace_id)


def ensure_nova_chat_session(
    db: Session,
    agent: Agent,
    runtime_session_id: str,
    workspace_id: str | None,
    _title: str,
) -> ChatSession:
    from app.agent_runtime.seeding.ensure_nova_chat_session import ensure_nova_chat_session as _action
    return _action(db, agent, runtime_session_id, workspace_id, _title)
