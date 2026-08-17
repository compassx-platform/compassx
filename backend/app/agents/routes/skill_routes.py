"""Skills CRUD and agent attachment routes."""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload

from app.database import get_system_db as get_db
from app.models.agents import Agent, Skill, AgentSkillAttachment
from app.schemas.agents import (
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    AgentSkillResponse,
)

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_skill(db: Session, skill_id: int, workspace_id: str | None = None) -> Skill:
    query = db.query(Skill).filter(Skill.id == skill_id, Skill.is_active.is_(True))
    if workspace_id:
        query = query.filter(Skill.workspace_id == workspace_id)
    else:
        query = query.filter(Skill.workspace_id == None)
    skill = query.first()
    if not skill:
        raise HTTPException(404, "Skill not found")
    return skill


@router.get("", response_model=list[SkillResponse])
def list_skills(
    request: Request,
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """List all active skills. Optional search by name or description."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    print("ROUTE WORKSPACE_ID:", workspace_id)
    query = db.query(Skill).filter(Skill.is_active.is_(True))
    if workspace_id:
        query = query.filter(Skill.workspace_id == workspace_id)
    else:
        query = query.filter(Skill.workspace_id == None)
    print("ROUTE QUERY:", str(query))
    print("ROUTE QUERY COMPILED:", str(query.statement.compile(compile_kwargs={"literal_binds": True})))
    res = query.order_by(Skill.name).all()
    print("ROUTE QUERY RESULT:", [(r.id, r.name, r.workspace_id) for r in res])
    return res


@router.post("", response_model=SkillResponse, status_code=201)
def create_skill(
    request: Request,
    body: SkillCreate,
    db: Session = Depends(get_db),
):
    """Create a new skill."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    # Check uniqueness of name (case-insensitive) within this workspace context
    query = db.query(Skill).filter(Skill.name.ilike(body.name), Skill.is_active.is_(True))
    if workspace_id:
        query = query.filter(Skill.workspace_id == workspace_id)
    else:
        query = query.filter(Skill.workspace_id == None)
    existing = query.first()
    if existing:
        raise HTTPException(400, "Skill with this name already exists")

    skill = Skill(
        workspace_id=workspace_id,
        name=body.name.strip(),
        description=body.description.strip(),
        body=body.body,
        trigger_hints=body.trigger_hints,
        version=1,
        is_active=True,
        created_by="system",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(
    request: Request,
    skill_id: int,
    db: Session = Depends(get_db),
):
    """Get a single skill by ID."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    return _get_skill(db, skill_id, workspace_id)


@router.put("/{skill_id}", response_model=SkillResponse)
def update_skill(
    request: Request,
    skill_id: int,
    body: SkillUpdate,
    db: Session = Depends(get_db),
):
    """Update a skill. Increments the version field."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    skill = _get_skill(db, skill_id, workspace_id)
    
    if body.name is not None:
        name_clean = body.name.strip()
        if name_clean.lower() != skill.name.lower():
            # Check unique constraints within workspace
            query = db.query(Skill).filter(Skill.name.ilike(name_clean), Skill.is_active.is_(True))
            if workspace_id:
                query = query.filter(Skill.workspace_id == workspace_id)
            else:
                query = query.filter(Skill.workspace_id == None)
            existing = query.first()
            if existing:
                raise HTTPException(400, "Skill with this name already exists")
        skill.name = name_clean

    if body.description is not None:
        skill.description = body.description.strip()

    if body.body is not None:
        skill.body = body.body

    if body.trigger_hints is not None:
        skill.trigger_hints = body.trigger_hints

    # Increment version upon update
    skill.version += 1
    skill.updated_at = _utcnow()
    
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=204)
def delete_skill(
    request: Request,
    skill_id: int,
    db: Session = Depends(get_db),
):
    """Soft delete a skill by setting is_active = False."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    skill = _get_skill(db, skill_id, workspace_id)
    skill.is_active = False
    skill.updated_at = _utcnow()
    
    # Detach from all agents
    db.query(AgentSkillAttachment).filter(AgentSkillAttachment.skill_id == skill_id).delete()
    
    db.commit()
    return


@router.post("/{skill_id}/attach/{agent_id}", response_model=AgentSkillResponse, status_code=201)
def attach_skill(
    request: Request,
    skill_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
):
    """Attach a skill to an agent."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    _get_skill(db, skill_id, workspace_id)
    
    agent_query = db.query(Agent).filter(Agent.id == agent_id)
    if workspace_id:
        agent_query = agent_query.filter(Agent.workspace_id == workspace_id)
    else:
        agent_query = agent_query.filter(Agent.workspace_id == None)
    agent = agent_query.first()
    if not agent:
        raise HTTPException(404, "Agent not found")
        
    # Check if already attached
    existing = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.skill_id == skill_id,
        AgentSkillAttachment.agent_id == agent_id,
    ).first()
    if existing:
        return db.query(AgentSkillAttachment).options(selectinload(AgentSkillAttachment.skill)).filter(
            AgentSkillAttachment.id == existing.id
        ).first()

    # Get max position
    max_pos = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.agent_id == agent_id
    ).count()

    attachment = AgentSkillAttachment(
        agent_id=agent_id,
        skill_id=skill_id,
        position=max_pos,
        attached_at=_utcnow(),
    )
    db.add(attachment)
    db.commit()
    
    return db.query(AgentSkillAttachment).options(selectinload(AgentSkillAttachment.skill)).filter(
        AgentSkillAttachment.id == attachment.id
    ).first()


@router.post("/{skill_id}/detach/{agent_id}", status_code=204)
def detach_skill(
    request: Request,
    skill_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
):
    """Detach a skill from an agent."""
    workspace_id = getattr(request.state, "workspace", None) and request.state.workspace.workspace_id
    _get_skill(db, skill_id, workspace_id)
    
    agent_query = db.query(Agent).filter(Agent.id == agent_id)
    if workspace_id:
        agent_query = agent_query.filter(Agent.workspace_id == workspace_id)
    else:
        agent_query = agent_query.filter(Agent.workspace_id == None)
    agent = agent_query.first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    attachment = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.skill_id == skill_id,
        AgentSkillAttachment.agent_id == agent_id,
    ).first()
    if not attachment:
        raise HTTPException(404, "Attachment not found")
        
    db.delete(attachment)
    db.commit()
    return
