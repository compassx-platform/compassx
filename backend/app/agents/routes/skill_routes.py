"""Skills CRUD and agent attachment routes.

A skill is a named block of instructions that agents can be given. It is not a
securable of its own: it holds no credential and reaches no data, and it only
has an effect once attached to an agent, which is where the grants live.

So the model here is two-sided:

  * the **skill library** is workspace-level configuration — any member may
    read it, and changing it is an admin act, because a skill is shared and
    editing one silently changes the behaviour of every agent it is attached
    to, including agents the editor holds no grant on;
  * **attaching or detaching** a skill is a change to an agent's definition,
    and so takes ``EDIT`` on that agent, exactly like editing its prompt.

Every lookup is scoped to ``guard.workspace_id``. The previous version fell
back to ``workspace_id == None`` whenever no workspace was resolved, so an
unscoped request reached the workspace-less skills instead of being refused.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload

from app.agents.routes._authz import authorized_agent
from app.database import get_system_db as get_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
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


def _get_skill(db: Session, skill_id: int, guard: Guard) -> Skill:
    """Load an active skill from the caller's workspace."""
    skill = (
        db.query(Skill)
        .filter(
            Skill.id == skill_id,
            Skill.is_active.is_(True),
            Skill.workspace_id == guard.workspace_id,
        )
        .first()
    )
    if not skill:
        raise HTTPException(404, "Skill not found")
    return skill


@router.get("", response_model=list[SkillResponse])
def list_skills(
    request: Request,
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the active skills in this workspace.

    Readable by any member: the library is what someone picks from when
    configuring an agent, and a skill body is instructions, not data.
    """
    query = db.query(Skill).filter(
        Skill.is_active.is_(True),
        Skill.workspace_id == guard.workspace_id,
    )
    if isinstance(search, str) and search.strip():
        query = query.filter(
            Skill.name.ilike(f"%{search.strip()}%") | Skill.description.ilike(f"%{search.strip()}%")
        )
    return query.order_by(Skill.name).all()


@router.post("", response_model=SkillResponse, status_code=201)
def create_skill(
    request: Request,
    body: SkillCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Add a skill to the workspace library.

    Admin: the library is shared, and anyone who can add to it can put text in
    front of an agent that other people will later attach without reading.
    """
    guard.require_workspace_admin("Creating a skill")
    workspace_id = guard.workspace_id
    existing = (
        db.query(Skill)
        .filter(
            Skill.name.ilike(body.name),
            Skill.is_active.is_(True),
            Skill.workspace_id == workspace_id,
        )
        .first()
    )
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
        created_by=str(guard.principal.id),
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
    guard: Guard = Depends(get_guard),
):
    """Get a single skill by ID."""
    return _get_skill(db, skill_id, guard)


@router.put("/{skill_id}", response_model=SkillResponse)
def update_skill(
    request: Request,
    skill_id: int,
    body: SkillUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Update a skill. Increments the version field.

    Admin, for the reason given in the module docstring: the edit propagates
    to every agent this skill is attached to, whoever owns them.
    """
    guard.require_workspace_admin("Editing a skill")
    skill = _get_skill(db, skill_id, guard)

    if body.name is not None:
        name_clean = body.name.strip()
        if name_clean.lower() != skill.name.lower():
            existing = (
                db.query(Skill)
                .filter(
                    Skill.name.ilike(name_clean),
                    Skill.is_active.is_(True),
                    Skill.workspace_id == guard.workspace_id,
                )
                .first()
            )
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
    guard: Guard = Depends(get_guard),
):
    """Soft delete a skill by setting is_active = False.

    Admin: it detaches the skill from every agent that had it, which changes
    the behaviour of agents belonging to other people.
    """
    guard.require_workspace_admin("Deleting a skill")
    skill = _get_skill(db, skill_id, guard)
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
    guard: Guard = Depends(get_guard),
):
    """Attach a skill to an agent.

    EDIT on the agent — this is an edit to its instructions, reached by a
    different URL. Reading the library takes nothing beyond membership, so the
    skill lookup adds no check of its own.
    """
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    _get_skill(db, skill_id, guard)

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
    guard: Guard = Depends(get_guard),
):
    """Detach a skill from an agent."""
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    _get_skill(db, skill_id, guard)

    attachment = db.query(AgentSkillAttachment).filter(
        AgentSkillAttachment.skill_id == skill_id,
        AgentSkillAttachment.agent_id == agent_id,
    ).first()
    if not attachment:
        raise HTTPException(404, "Attachment not found")

    db.delete(attachment)
    db.commit()
    return
