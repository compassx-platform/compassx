"""Document Upload API Routes — Part F of AI Data Engineer Spec v5.

Endpoints:
  POST   /agents/{agent_id}/sessions/{session_id}/documents   — upload file(s)
  GET    /agents/{agent_id}/sessions/{session_id}/documents   — list session docs
  DELETE /agents/{agent_id}/sessions/{session_id}/documents/{doc_id} — remove doc

Uploaded files are stored, extracted, embedded (background task), and their
doc_id is linked into the active plan's context.uploaded_documents if one exists.
"""

from __future__ import annotations

import logging

import os

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_session

from app.database import get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.models.agents import Agent, ChatSession, RagDocument, DocumentStatus

from app.agents.services.document_processor import parse_document, process_document

from app.agents.services.agent.plan_service import PlanService

logger = logging.getLogger("app.agents.routes.document_routes")

ACCEPTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "text/plain",
    "text/markdown",
    "application/json",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
}

def _get_session_or_404(
    db: Session, agent_id: int, session_id: int, guard: Guard, privilege: Privilege
) -> ChatSession:
    """Load a session, having authorised the agent that owns it.

    Uploaded files become part of what the agent reads, so they are governed
    by the agent. The bare id lookup this replaces had no workspace filter at
    all — session ids are globally unique, so any session's evidence pool was
    both readable and writable by anyone who could guess an id.
    """
    return authorized_session(db, guard, agent_id, session_id, privilege)

def _link_doc_to_plan(session_id: int, doc_id: int) -> None:
    """Add doc_id to the active plan's context.uploaded_documents if one exists."""
    try:
        plan_svc = PlanService()
        active_plan = plan_svc.get_active_plan_for_session(session_id)
        if active_plan:
            doc_ref = str(doc_id)
            if doc_ref not in active_plan.context.uploaded_documents:
                active_plan.context.uploaded_documents.append(doc_ref)
                plan_svc.save_plan(active_plan)
                logger.info("Linked doc %s to plan %s", doc_id, active_plan.plan_id)
    except Exception as exc:
        logger.warning("Could not link doc to plan: %s", exc)
