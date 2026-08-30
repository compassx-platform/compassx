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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents/{agent_id}/sessions/{session_id}", tags=["Artifacts"])


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Known-assets registry ─────────────────────────────────────────────────────

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
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    entries = known_assets_registry.get_all(session_id)
    if not entries:
        from app.models.agents import ChatMessage, MessageRole
        from app.agents.services.agent.known_assets_registry import register_from_tool_result
        tool_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == MessageRole.tool)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        for msg in tool_messages:
            if msg.tool_result and isinstance(msg.tool_result, dict):
                res = msg.tool_result.get("result") or {}
                if isinstance(res, dict) and msg.tool_name:
                    register_from_tool_result(session_id, msg.tool_name, res)
        entries = known_assets_registry.get_all(session_id)

    return [
        {
            "full_name": e.full_name,
            "object_type": e.object_type,
            "first_seen_turn": e.first_seen_turn,
            "source": e.source,
            "action": e.action,
            "plan_id": e.plan_id,
            "url": _resolve_asset_url(e.full_name, e.object_type),
        }
        for e in entries
    ]


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


# ── Change records ────────────────────────────────────────────────────────────

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
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    records = get_changes_for_session(db, session_id, step_id=step_id)
    # Enrich with resolved URL
    for r in records:
        r["url"] = _resolve_asset_url(r["full_name"], r["object_type"])
    return records


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
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    record = get_change_record(db, change_id)
    if not record:
        raise HTTPException(404, f"Change {change_id} not found")
    record["url"] = _resolve_asset_url(record["full_name"], record["object_type"])
    return record


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
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    result = accept_change(db, change_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Accept failed"))
    return result


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
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    result = reject_change(db, change_id, session_id)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "Reject failed"))
    return result


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
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    action = body.get("action", "accept_all")
    if action not in ("accept_all", "reject_all"):
        raise HTTPException(400, "action must be 'accept_all' or 'reject_all'")
    return bulk_review_changes(db, session_id, action)
