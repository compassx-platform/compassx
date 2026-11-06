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

def _get_or_404(db: Session, agent_id: int, entry_id: int) -> AgentContextEntry:
    entry = db.query(AgentContextEntry).filter(AgentContextEntry.id == entry_id, AgentContextEntry.agent_id == agent_id).first()
    if not entry:
        raise HTTPException(404, "Context entry not found")
    return entry

import app.agents.http.context.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.context.application.list_agent_context import list_agent_context as list_agent_context_action
from app.agents.http.context.application.add_agent_context import add_agent_context as add_agent_context_action
from app.agents.http.context.application.update_agent_context import update_agent_context as update_agent_context_action
from app.agents.http.context.application.delete_agent_context import delete_agent_context as delete_agent_context_action

router = APIRouter(prefix="/api/v1/agents/{agent_id}/context", tags=["Agent Context"])

@router.get("", response_model=list[AgentContextEntryResponse])
def list_agent_context(
    agent_id: int,
    active_only: bool = True,
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List an agent's standing context entries."""
    return list_agent_context_action(agent_id=agent_id, active_only=active_only, search=search, db=db, guard=guard)

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
    return add_agent_context_action(agent_id=agent_id, body=body, db=db, guard=guard)

@router.put("/{entry_id}", response_model=AgentContextEntryResponse)
def update_agent_context(
    agent_id: int,
    entry_id: int,
    body: ContextEntryUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return update_agent_context_action(agent_id=agent_id, entry_id=entry_id, body=body, db=db, guard=guard)

@router.delete("/{entry_id}", status_code=204)
def delete_agent_context(
    agent_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return delete_agent_context_action(agent_id=agent_id, entry_id=entry_id, db=db, guard=guard)
