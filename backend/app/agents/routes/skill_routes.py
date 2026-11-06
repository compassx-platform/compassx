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

import app.agents.http.skills.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.skills.application.list_skills import list_skills as list_skills_action
from app.agents.http.skills.application.create_skill import create_skill as create_skill_action
from app.agents.http.skills.application.get_skill import get_skill as get_skill_action
from app.agents.http.skills.application.update_skill import update_skill as update_skill_action
from app.agents.http.skills.application.delete_skill import delete_skill as delete_skill_action
from app.agents.http.skills.application.attach_skill import attach_skill as attach_skill_action
from app.agents.http.skills.application.detach_skill import detach_skill as detach_skill_action

router = APIRouter(prefix="/api/v1/skills", tags=["Skills"])

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
    return list_skills_action(request=request, search=search, db=db, guard=guard)

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
    return create_skill_action(request=request, body=body, db=db, guard=guard)

@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(
    request: Request,
    skill_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Get a single skill by ID."""
    return get_skill_action(request=request, skill_id=skill_id, db=db, guard=guard)

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
    return update_skill_action(request=request, skill_id=skill_id, body=body, db=db, guard=guard)

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
    return delete_skill_action(request=request, skill_id=skill_id, db=db, guard=guard)

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
    return attach_skill_action(request=request, skill_id=skill_id, agent_id=agent_id, db=db, guard=guard)

@router.post("/{skill_id}/detach/{agent_id}", status_code=204)
def detach_skill(
    request: Request,
    skill_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Detach a skill from an agent."""
    return detach_skill_action(request=request, skill_id=skill_id, agent_id=agent_id, db=db, guard=guard)
