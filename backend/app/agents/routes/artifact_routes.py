"""Artifact Visibility API Routes — Part G of AI Data Engineer Spec v5.

Endpoints:
  GET  /agents/{agent_id}/sessions/{session_id}/assets              — known-assets registry dump
  GET  /agents/{agent_id}/sessions/{session_id}/changes             — change records for session
  POST /agents/{agent_id}/sessions/{session_id}/changes/{id}/accept — accept a change (D20)
  POST /agents/{agent_id}/sessions/{session_id}/changes/{id}/reject — reject/revert a change (D20)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_session

from app.database import get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.models.agents import ChatSession

from app.agents.services.agent.known_assets_registry import registry as known_assets_registry

from app.agents.services.agent.change_capture_service import (
    accept_change,
    reject_change,
    bulk_review_changes,
    get_changes_for_session,
    get_change_record,
)

logger = logging.getLogger("app.agents.routes.artifact_routes")

def _get_session_or_404(
    db: Session, agent_id: int, session_id: int, guard: Guard, privilege: Privilege
) -> ChatSession:
    """Load a session, having authorised the agent that owns it.

    The bare id lookup this replaces was not scoped to a workspace at all:
    session ids are globally unique, so any session in the deployment resolved
    — including its change records, which carry the before and after content
    of the objects the agent rewrote.
    """
    return authorized_session(db, guard, agent_id, session_id, privilege)

def _resolve_asset_url(full_name: str, object_type: str) -> str:
    """G4: canonical URL resolver — /catalog/{catalog}/{schema}/{object}?type={type}"""
    parts = full_name.split(".")
    if len(parts) == 3:
        catalog, schema, obj = parts
        return f"/catalog/{catalog}/{schema}/{obj}?type={object_type}"
    elif len(parts) == 2:
        schema, obj = parts
        return f"/catalog/{schema}/{obj}?type={object_type}"
    return f"/catalog?q={full_name}"

import app.agents.http.artifacts.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.artifacts.application.list_session_assets import list_session_assets as list_session_assets_action
from app.agents.http.artifacts.application.list_changes import list_changes as list_changes_action
from app.agents.http.artifacts.application.get_change_endpoint import get_change_endpoint as get_change_endpoint_action
from app.agents.http.artifacts.application.accept_change_endpoint import accept_change_endpoint as accept_change_endpoint_action
from app.agents.http.artifacts.application.reject_change_endpoint import reject_change_endpoint as reject_change_endpoint_action
from app.agents.http.artifacts.application.bulk_review_endpoint import bulk_review_endpoint as bulk_review_endpoint_action

logger = logging.getLogger("app.agents.routes.artifact_routes")

router = APIRouter(prefix="/api/v1/agents/{agent_id}/sessions/{session_id}", tags=["Artifacts"])

@router.get("/assets")
def list_session_assets(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return all assets registered in the known-assets registry for this session (G1).

    BROWSE on the agent — this is a list of the catalog objects the agent
    touched during the conversation, which is part of the transcript.
    """
    return list_session_assets_action(request=request, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.get("/changes")
def list_changes(
    request: Request,
    agent_id: int,
    session_id: int,
    step_id: int | None = None,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return change records for this session, optionally filtered by plan step (G5)."""
    return list_changes_action(request=request, agent_id=agent_id, session_id=session_id, step_id=step_id, db=db, guard=guard)

@router.get("/changes/{change_id}")
def get_change_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    change_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return a single change record with full before/after content (G5).

    The response is the previous and new definition of a catalog object, so a
    caller who could reach this without BROWSE on the agent would be reading
    object content through the change log.
    """
    return get_change_endpoint_action(request=request, agent_id=agent_id, session_id=session_id, change_id=change_id, db=db, guard=guard)

@router.post("/changes/{change_id}/accept")
def accept_change_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    change_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Accept a change record — sets status to 'accepted', no further write (D20).

    EXECUTE, not BROWSE: accepting is a review decision that settles what the
    agent did, and it takes the same privilege as having run the turn.
    """
    return accept_change_endpoint_action(request=request, agent_id=agent_id, session_id=session_id, change_id=change_id, db=db, guard=guard)

@router.post("/changes/{change_id}/reject")
def reject_change_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    change_id: str,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Reject a change — re-applies before content and creates a new revert record (D20).

    EXECUTE: this writes the previous content back to the catalog object, so
    it is the agent acting again, under the same delegation.
    """
    return reject_change_endpoint_action(request=request, agent_id=agent_id, session_id=session_id, change_id=change_id, db=db, guard=guard)

@router.post("/changes/bulk-review")
def bulk_review_endpoint(
    request: Request,
    agent_id: int,
    session_id: int,
    body: dict,  # {"action": "accept_all" | "reject_all"}
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Bulk accept or reject all pending changes for a session."""
    return bulk_review_endpoint_action(request=request, agent_id=agent_id, session_id=session_id, body=body, db=db, guard=guard)
