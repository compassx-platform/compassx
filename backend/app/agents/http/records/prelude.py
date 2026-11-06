"""Agent Builder CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.orm import Session, selectinload

from app.agents.routes._authz import authorized_agent, visible_agents

from app.database import get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.governance.securable import Securable

from app.models.agents import Agent, AgentTool, AgentSkillAttachment

from app.schemas.agents import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentToolResponse,
    AgentUpdate,
    AgentSkillResponse,
    SkillResponse,
)

def _load_agent(db: Session, agent_id: int, guard: Guard, privilege: Privilege) -> Agent:
    """Load an agent the caller holds ``privilege`` on, with tools and skills.

    Scoped to the guard's workspace before the grant check. The previous
    version fell back to ``Agent.workspace_id == None`` whenever no workspace
    was resolved, which meant an unscoped request reached the workspace-less
    agents rather than being refused.
    """
    authorized_agent(db, guard, agent_id, privilege)
    return (
        db.query(Agent)
        .options(
            selectinload(Agent.tools),
            selectinload(Agent.skills).selectinload(AgentSkillAttachment.skill),
        )
        .filter(Agent.id == agent_id)
        .first()
    )

def _agent_response(agent: Agent) -> AgentResponse:
    resp = AgentResponse.model_validate(agent)
    resp.tools = [AgentToolResponse(id=t.id, tool_name=t.tool_name) for t in agent.tools]
    resp.skills = [
        AgentSkillResponse(
            id=s.id,
            agent_id=s.agent_id,
            skill_id=s.skill_id,
            position=s.position,
            attached_at=s.attached_at,
            skill=SkillResponse.model_validate(s.skill)
        )
        for s in sorted(agent.skills, key=lambda x: x.position)
        if s.skill.is_active
    ]
    return resp

def _sync_tools(db: Session, agent_id: int, tools) -> None:
    for t in (tools or []):
        db.add(AgentTool(
            agent_id=agent_id,
            tool_name=t.tool_name if hasattr(t, "tool_name") else t["tool_name"],
        ))

def _sync_skills(db: Session, agent_id: int, skills) -> None:
    for idx, s in enumerate(skills or []):
        db.add(AgentSkillAttachment(
            agent_id=agent_id,
            skill_id=s.skill_id if hasattr(s, "skill_id") else s["skill_id"],
            position=idx,
        ))
