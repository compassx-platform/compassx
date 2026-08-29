"""Agent Builder CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from app.database import get_system_db as get_db
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


def _load_agent(db: Session, agent_id: int, workspace_id: str | None = None) -> Agent:
    query = (
        db.query(Agent)
        .options(
            selectinload(Agent.tools),
            selectinload(Agent.skills).selectinload(AgentSkillAttachment.skill),
        )
        .filter(Agent.id == agent_id)
    )
    if workspace_id:
        query = query.filter(Agent.workspace_id == workspace_id)
    else:
        query = query.filter(Agent.workspace_id == None)
    agent = query.first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


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
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    query = db.query(Agent)
    if workspace_id:
        query = query.filter(Agent.workspace_id == workspace_id)
    else:
        query = query.filter(Agent.workspace_id == None)
        
    agents = (
        query
        .options(selectinload(Agent.tools))
        .order_by(Agent.name)
        .all()
    )
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
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
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
        created_by="system",
    )
    db.add(agent)
    db.flush()
    _sync_tools(db, agent.id, body.tools)
    _sync_skills(db, agent.id, body.skills)
    db.commit()
    return _agent_response(_load_agent(db, agent.id, workspace_id))


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return _agent_response(_load_agent(db, agent_id, workspace_id))


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    request: Request,
    agent_id: int,
    body: AgentUpdate,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    agent = _load_agent(db, agent_id, workspace_id)
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
    return _agent_response(_load_agent(db, agent_id, workspace_id))


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    agent = _load_agent(db, agent_id, workspace_id)
    db.delete(agent)
    db.commit()


@router.post("/{agent_id}/clone", response_model=AgentResponse, status_code=201)
def clone_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
):
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    source = _load_agent(db, agent_id, workspace_id)

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
        created_by="system",
    )
    db.add(clone)
    db.flush()

    for tool in source.tools:
        db.add(AgentTool(agent_id=clone.id, tool_name=tool.tool_name))
    for s in source.skills:
        db.add(AgentSkillAttachment(agent_id=clone.id, skill_id=s.skill_id, position=s.position))

    db.commit()
    return _agent_response(_load_agent(db, clone.id, workspace_id))


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
