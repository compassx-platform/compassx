"""Unit tests for the 3-Tier Layered Prompt Context Builder."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import SystemBase
from app.models.agents import Agent, ChatSession, AgentContextEntry, RagDocument, DocumentStatus, Skill, AgentSkillAttachment
from app.agents.services.agent.context_builder import build_agent_system_prompt, build_system_prompt, PromptResult
from app.agents.services.agent.system_prompts import PLATFORM_AGENT_OS_PROMPT, SKILLS_STANDING_INSTRUCTION


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"jobs": None, "ai": None, "auth": None, "catalog": None}},
        poolclass=StaticPool,
    )
    SystemBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.close()


def test_base_agent_os_prompt_default(db_session):
    agent = Agent(name="DefaultAgent", prompt=None)
    db_session.add(agent)
    db_session.commit()

    res: PromptResult = build_agent_system_prompt(db_session, agent)
    assert res.system_prompt.startswith("You are an AI Agent on the CompassX platform.")
    assert "## Custom Agent Persona & Domain Instructions" not in res.system_prompt
    assert res.has_attachment_tool_fetch is False


def test_user_custom_instructions_layering(db_session):
    custom_instructions = "You are a specialized Risk Auditor focusing on credit risk."
    agent = Agent(name="RiskAgent", prompt=custom_instructions)
    db_session.add(agent)
    db_session.commit()

    res: PromptResult = build_agent_system_prompt(db_session, agent)
    # Layer 1: Platform Agent OS is present
    assert "You are an AI Agent on the CompassX platform." in res.system_prompt
    # Layer 2: Custom user instructions are layered
    assert "## Custom Agent Persona & Domain Instructions" in res.system_prompt
    assert custom_instructions in res.system_prompt


def test_agent_context_and_skills_layering(db_session):
    agent = Agent(name="SkilledAgent", prompt="Help with ETL pipelines.")
    db_session.add(agent)
    db_session.commit()

    ctx = AgentContextEntry(
        agent_id=agent.id,
        text="Production database is pg_main. Use read-only replica for queries.",
        version=1,
        is_active=True,
    )
    skill = Skill(name="dbt_run", description="Runs dbt models", body="dbt run --select staging")
    db_session.add_all([ctx, skill])
    db_session.commit()

    att = AgentSkillAttachment(agent_id=agent.id, skill_id=skill.id, position=0)
    db_session.add(att)
    db_session.commit()
    db_session.refresh(agent)

    res: PromptResult = build_agent_system_prompt(db_session, agent)
    assert "## Agent Workspace Context" in res.system_prompt
    assert "Production database is pg_main." in res.system_prompt
    assert "## Available Skills" in res.system_prompt


def test_session_attachments_and_tool_fetch(db_session):
    agent = Agent(name="VisionDocAgent", prompt=None)
    db_session.add(agent)
    db_session.commit()

    chat_session = ChatSession(agent_id=agent.id, title="Doc Session")
    db_session.add(chat_session)
    db_session.commit()

    # Add a PDF document that requires tool_fetch
    pdf_doc = RagDocument(
        agent_id=agent.id,
        session_id=chat_session.id,
        filename="balance_sheet.pdf",
        mime_type="application/pdf",
        size_bytes=50000,
        status=DocumentStatus.ready,
        extracted_preview="[PDF Document: balance_sheet.pdf | Total Pages: 5]",
    )
    # Add an Image document
    img_doc = RagDocument(
        agent_id=agent.id,
        session_id=chat_session.id,
        filename="org_chart.png",
        mime_type="image/png",
        size_bytes=12000,
        status=DocumentStatus.ready,
        extracted_preview="[Image Document: org_chart.png (image/png) | Size: 12000 bytes]",
    )
    db_session.add_all([pdf_doc, img_doc])
    db_session.commit()

    res: PromptResult = build_agent_system_prompt(db_session, agent, session_id=chat_session.id)
    assert "## Attached Session Files" in res.system_prompt
    assert "### Attached Document: balance_sheet.pdf" in res.system_prompt
    assert "### Attached Image: org_chart.png" in res.system_prompt
    assert "fetch_attachment" in res.system_prompt
    assert res.has_attachment_tool_fetch is True
