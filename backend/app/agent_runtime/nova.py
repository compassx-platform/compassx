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
    query = db.query(Agent).options(selectinload(Agent.tools), selectinload(Agent.skills))
    if workspace_id:
        query = query.filter(Agent.workspace_id == workspace_id)
    agent = query.filter(Agent.name == NOVA_NAME).order_by(Agent.id.asc()).first()
    if agent:
        existing = {tool.tool_name for tool in agent.tools}
        for key in NOVA_TOOLS:
            if key not in existing:
                db.add(AgentTool(agent_id=agent.id, tool_name=key))
        db.commit()
        return (
            db.query(Agent)
            .options(selectinload(Agent.tools), selectinload(Agent.skills))
            .filter(Agent.id == agent.id)
            .first()
        )
    agent = Agent(
        workspace_id=workspace_id,
        name=NOVA_NAME,
        description="CompassX default agent for data, notebooks, and analysis.",
        color=NOVA_COLOR,
        prompt="",
        is_orchestrator=True,
        visibility=AgentVisibility.shared,
        status="active",
        is_active=True,
        created_by="system",
        manifest={},
    )
    db.add(agent)
    db.flush()
    for key in NOVA_TOOLS:
        db.add(AgentTool(agent_id=agent.id, tool_name=key))
    db.commit()
    return (
        db.query(Agent)
        .options(selectinload(Agent.tools), selectinload(Agent.skills))
        .filter(Agent.id == agent.id)
        .first()
    )


def ensure_nova_chat_session(
    db: Session,
    agent: Agent,
    runtime_session_id: str,
    workspace_id: str | None,
    _title: str,
) -> ChatSession:
    marker = runtime_chat_title(runtime_session_id)
    session = (
        db.query(ChatSession)
        .filter(ChatSession.agent_id == agent.id, ChatSession.title == marker)
        .first()
    )
    if session:
        return session
    session = ChatSession(
        workspace_id=workspace_id,
        agent_id=agent.id,
        title=marker,
        archived=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
