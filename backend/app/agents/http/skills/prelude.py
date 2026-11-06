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
