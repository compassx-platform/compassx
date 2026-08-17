"""Assemble the system prompt for an agent turn.

Order of injection:
  1. Shared business context (active entries, sorted by version desc)
  2. Agent context entries (active, sorted by version desc)
  3. Agent's own system_prompt field
  4. standing instructions for skills (if skills are attached)

This is called once per orchestrator turn — before the LLM call.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.agents import Agent, AgentContextEntry
from app.agents.services.agent.system_prompts import AI_DATA_ENGINEER_SYSTEM_PROMPT


def build_system_prompt(db: Session, agent: Agent) -> str:
    """Return the fully assembled system prompt string."""
    parts: list[str] = []

    # 2. Agent-specific context
    agent_entries = (
        db.query(AgentContextEntry)
        .filter(
            AgentContextEntry.agent_id == agent.id,
            AgentContextEntry.is_active.is_(True),
        )
        .order_by(AgentContextEntry.version.desc())
        .all()
    )
    if agent_entries:
        ctx_text = "\n".join(e.text for e in agent_entries)
        parts.append(f"## Agent Context\n{ctx_text}")

    # 3. Agent system prompt (fallback to Spec v2 AI Data Engineer system prompt)
    if agent.prompt:
        parts.append(agent.prompt)
    else:
        parts.append(AI_DATA_ENGINEER_SYSTEM_PROMPT)

    # 4. Standing instruction for skills
    if hasattr(agent, "skills") and agent.skills:
        skills_instruction = (
            "## Available Skills\n"
            "You have access to specialized procedural skills. You MUST search/list available skills using "
            "`list_available_skills` first to find the relevant skill, then retrieve its step-by-step instructions "
            "using `read_skill` before performing any complex workflow or execution. Do not assume you know "
            "the instructions without reading them first."
        )
        parts.append(skills_instruction)

    return "\n\n---\n\n".join(parts) if parts else "You are a helpful AI assistant."
