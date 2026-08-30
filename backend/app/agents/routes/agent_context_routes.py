"""Agent-level context entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_agent
from app.database import get_system_db as get_db
from app.governance.dependencies import Guard, get_guard
from app.governance.privileges import Privilege
from app.models.agents import Agent, AgentContextEntry
from app.schemas.agents import AgentContextEntryResponse, ContextEntryCreate, ContextEntryUpdate

router = APIRouter(prefix="/api/v1/agents/{agent_id}/context", tags=["Agent Context"])

# Context entries are standing instructions injected into every run of an
# agent, so they are part of what the agent does — governed by the agent, at
# the same privileges as its prompt. They have no workspace_id of their own;
# resolving the agent first is what scopes them.


@router.get("", response_model=list[AgentContextEntryResponse])
def list_agent_context(
    agent_id: int,
    active_only: bool = True,
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List an agent's standing context entries."""
    authorized_agent(db, guard, agent_id, Privilege.BROWSE)
    q = db.query(AgentContextEntry).filter(AgentContextEntry.agent_id == agent_id)
    if active_only:
        q = q.filter(AgentContextEntry.is_active.is_(True))
    if search:
        q = q.filter(AgentContextEntry.text.ilike(f"%{search}%"))
    return q.order_by(AgentContextEntry.created_at.desc()).all()


@router.post("", response_model=AgentContextEntryResponse, status_code=201)
def add_agent_context(
    agent_id: int,
    body: ContextEntryCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Add a standing instruction to an agent.

    EDIT, because this text is prepended to every subsequent run: it changes
    what the agent does for everyone who may execute it.
    """
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    entry = AgentContextEntry(
        agent_id=agent_id,
        text=body.text,
        tags=body.tags,
        created_by=str(guard.principal.id),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/{entry_id}", response_model=AgentContextEntryResponse)
def update_agent_context(
    agent_id: int,
    entry_id: int,
    body: ContextEntryUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    entry = _get_or_404(db, agent_id, entry_id)
    if body.text and body.text != entry.text:
        entry.is_active = False
        new_entry = AgentContextEntry(
            agent_id=agent_id,
            text=body.text,
            tags=body.tags if body.tags is not None else entry.tags,
            version=entry.version + 1,
            is_active=True,
            created_by=str(guard.principal.id),
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return new_entry
    if body.tags is not None:
        entry.tags = body.tags
    if body.is_active is not None:
        entry.is_active = body.is_active
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_agent_context(
    agent_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    entry = _get_or_404(db, agent_id, entry_id)
    db.delete(entry)
    db.commit()


def _get_or_404(db: Session, agent_id: int, entry_id: int) -> AgentContextEntry:
    entry = db.query(AgentContextEntry).filter(AgentContextEntry.id == entry_id, AgentContextEntry.agent_id == agent_id).first()
    if not entry:
        raise HTTPException(404, "Context entry not found")
    return entry
