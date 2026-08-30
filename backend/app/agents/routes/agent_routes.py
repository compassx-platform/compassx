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

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


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


@router.get("", response_model=list[AgentListResponse])
def list_agents(
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the agents in this workspace that the caller may browse."""
    agents = (
        db.query(Agent)
        .filter(Agent.workspace_id == guard.workspace_id)
        .options(selectinload(Agent.tools))
        .order_by(Agent.name)
        .all()
    )
    agents = visible_agents(guard, agents)
    return [
        AgentListResponse(
            id=a.id,
            llm_connection_id=a.llm_connection_id,
            name=a.name,
            description=a.description,
            avatar=a.avatar,
            color=a.color,
            model=a.model,
            is_orchestrator=a.is_orchestrator,
            visibility=a.visibility,
            is_active=a.is_active,
            tool_count=len(a.tools),
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]


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
    guard.require_workspace_admin("Creating an agent")
    workspace_id = guard.workspace_id
    agent = Agent(
        workspace_id=workspace_id,
        llm_connection_id=body.llm_connection_id,
        name=body.name,
        description=body.description,
        avatar=body.avatar,
        color=body.color,
        prompt=body.prompt,
        model=body.model,
        max_tokens=body.max_tokens,
        is_orchestrator=body.is_orchestrator,
        visibility=body.visibility,
        created_by=str(guard.principal.id),
    )
    db.add(agent)
    db.flush()
    _sync_tools(db, agent.id, body.tools)
    _sync_skills(db, agent.id, body.skills)
    db.commit()
    guard.claim_ownership(Securable.agent(str(agent.id)))
    return _agent_response(_load_agent(db, agent.id, guard, Privilege.BROWSE))


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
    return _agent_response(_load_agent(db, agent_id, guard, Privilege.BROWSE))


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
    agent = _load_agent(db, agent_id, guard, Privilege.EDIT)
    data = body.model_dump(exclude_none=True)
    tools = data.pop("tools", None)
    data.pop("db_connections", None)
    data.pop("git_connections", None)
    skills = data.pop("skills", None)
    for field, value in data.items():
        setattr(agent, field, value)
    if tools is not None:
        db.query(AgentTool).filter(AgentTool.agent_id == agent_id).delete()
        _sync_tools(db, agent_id, tools)
    if skills is not None:
        db.query(AgentSkillAttachment).filter(AgentSkillAttachment.agent_id == agent_id).delete()
        _sync_skills(db, agent_id, skills)
    db.commit()
    return _agent_response(_load_agent(db, agent_id, guard, Privilege.BROWSE))


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
    agent = _load_agent(db, agent_id, guard, Privilege.MANAGE)
    db.delete(agent)
    db.commit()


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
    source = _load_agent(db, agent_id, guard, Privilege.BROWSE)
    guard.require_workspace_admin("Cloning an agent")
    workspace_id = guard.workspace_id

    clone = Agent(
        workspace_id=workspace_id,
        llm_connection_id=source.llm_connection_id,
        name=f"{source.name} (copy)",
        description=source.description,
        avatar=source.avatar,
        color=source.color,
        prompt=source.prompt,
        model=source.model,
        max_tokens=source.max_tokens,
        is_orchestrator=source.is_orchestrator,
        visibility=source.visibility,
        created_by=str(guard.principal.id),
    )
    db.add(clone)
    db.flush()

    for tool in source.tools:
        db.add(AgentTool(agent_id=clone.id, tool_name=tool.tool_name))
    for s in source.skills:
        db.add(AgentSkillAttachment(agent_id=clone.id, skill_id=s.skill_id, position=s.position))

    db.commit()
    # The clone is a new object: it starts with the caller as owner and no
    # grants, rather than inheriting the source's, whose grantees consented to
    # the source and not to a copy someone else now controls.
    guard.claim_ownership(Securable.agent(str(clone.id)))
    return _agent_response(_load_agent(db, clone.id, guard, Privilege.BROWSE))


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
