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

import app.agents.http.records.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.records.application.list_agents import list_agents as list_agents_action
from app.agents.http.records.application.create_agent import create_agent as create_agent_action
from app.agents.http.records.application.get_agent import get_agent as get_agent_action
from app.agents.http.records.application.update_agent import update_agent as update_agent_action
from app.agents.http.records.application.delete_agent import delete_agent as delete_agent_action
from app.agents.http.records.application.clone_agent import clone_agent as clone_agent_action

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])

@router.get("", response_model=list[AgentListResponse])
def list_agents(
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the agents in this workspace that the caller may browse."""
    return list_agents_action(request=request, db=db, guard=guard)

@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(
    request: Request,
    body: AgentCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Create an agent, owned by its creator.

    An agent holds its own grants and runs tools under its own identity, so
    bringing one into being is an admin action rather than something any
    member may do.
    """
    return create_agent_action(request=request, body=body, db=db, guard=guard)

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return an agent's definition.

    BROWSE, not EDIT: the response includes the system prompt, which is what
    someone deciding whether to run this agent needs to read.
    """
    return get_agent_action(request=request, agent_id=agent_id, db=db, guard=guard)

@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    request: Request,
    agent_id: int,
    body: AgentUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Change an agent's definition.

    EDIT covers the prompt, model, and tool list — that is, what the agent
    does and what it may reach. Anyone who can run the agent inherits the
    consequences, so it is deliberately not implied by EXECUTE.
    """
    return update_agent_action(request=request, agent_id=agent_id, body=body, db=db, guard=guard)

@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Delete an agent.

    Takes its chat history with it and cannot be undone by whoever was relying
    on it, so MANAGE rather than EDIT.
    """
    return delete_agent_action(request=request, agent_id=agent_id, db=db, guard=guard)

@router.post("/{agent_id}/clone", response_model=AgentResponse, status_code=201)
def clone_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Copy an agent into a new one owned by the caller.

    A clone reproduces the source's prompt and tool list verbatim, so it
    discloses exactly what BROWSE does. Creating the copy is still an admin
    action, for the same reason ``create_agent`` is.
    """
    return clone_agent_action(request=request, agent_id=agent_id, db=db, guard=guard)
