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
