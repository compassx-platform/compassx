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
