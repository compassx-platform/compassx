"""Chat session CRUD and SSE streaming endpoint."""

from __future__ import annotations

import asyncio

import contextlib

import json

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from app.agents.routes._authz import authorized_agent, authorized_session

from app.database import SystemSessionLocal as SessionLocal, get_system_db as get_db

from app.governance.dependencies import Guard, get_guard

from app.governance.privileges import Privilege

from app.models.agents import Agent, ChatMessage, ChatSession, MessageRole

from app.schemas.agents import (
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ContextUsageResponse,
    SendMessageRequest,
)

from app.agents.services.agent.orchestrator import _resolve_llm_connection, orchestrate_stream

from app.agents.services.agent.compactor import (
    DEFAULT_HIGH_WATERMARK_RATIO,
    DEFAULT_LOW_WATERMARK_K,
    estimate_messages_tokens,
    group_messages_into_turns,
    resolve_model_context_window,
)

from app.agents.services.stream_registry import stream_registry

logger = logging.getLogger("app.agents.routes.chat_routes")

def _get_agent_or_404(db: Session, agent_id: int, guard: Guard, privilege: Privilege) -> Agent:
    """Load an agent the caller holds ``privilege`` on.

    The workspace comes from the guard. The previous version fell back to
    ``Agent.workspace_id == None`` when no workspace was resolved, so an
    unscoped request reached the workspace-less agents instead of being
    refused.
    """
    return authorized_agent(db, guard, agent_id, privilege)

def _get_session_or_404(
    db: Session, agent_id: int, session_id: int, guard: Guard, privilege: Privilege
) -> ChatSession:
    """Load a session, having authorised the agent that owns it.

    Sessions carry no grants of their own: a session is a conversation with an
    agent, so the agent is the securable.
    """
    return authorized_session(db, guard, agent_id, session_id, privilege)

import app.agents.http.chat.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agents.http.chat.application.list_sessions import list_sessions as list_sessions_action
from app.agents.http.chat.application.create_session import create_session as create_session_action
from app.agents.http.chat.application.archive_session import archive_session as archive_session_action
from app.agents.http.chat.application.list_messages import list_messages as list_messages_action
from app.agents.http.chat.application.get_session_context import get_session_context as get_session_context_action
from app.agents.http.chat.application.list_session_plans import list_session_plans as list_session_plans_action
from app.agents.http.chat.application.get_latest_session_plan import get_latest_session_plan as get_latest_session_plan_action
from app.agents.http.chat.application.stream_chat import stream_chat as stream_chat_action

logger = logging.getLogger("app.agents.routes.chat_routes")

router = APIRouter(prefix="/api/v1/agents/{agent_id}", tags=["Chat"])

@router.get("/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List an agent's chat sessions, with a preview of the last message.

    Sessions belong to the agent rather than to the person who opened them, so
    BROWSE on the agent is what admits someone to the history. That is the
    existing product behaviour — a shared workspace for the agent — made
    explicit rather than changed.
    """
    return list_sessions_action(request=request, agent_id=agent_id, db=db, guard=guard)

@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    request: Request,
    agent_id: int,
    body: ChatSessionCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Open a conversation with an agent.

    EXECUTE, matching ``stream_chat``: a session exists to be run, and a
    principal who may not run the agent has no use for an empty one.
    """
    return create_session_action(request=request, agent_id=agent_id, body=body, db=db, guard=guard)

@router.delete("/sessions/{session_id}", status_code=204)
def archive_session(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Archive a session, hiding it from the session list.

    EXECUTE: sessions are shared per agent, so whoever may run the agent may
    tidy up the conversations on it. The history is retained, not deleted.
    """
    return archive_session_action(request=request, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return a session's transcript.

    Tool output is part of the transcript, so this can contain query results
    the agent read on someone else's behalf — hence a real check rather than
    the bare id lookup that used to be here.
    """
    return list_messages_action(request=request, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.get("/sessions/{session_id}/context", response_model=ContextUsageResponse)
def get_session_context(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Report how much of the model's context window this session is using.

    The response includes the rolling summary, which is a condensation of the
    transcript — so it takes the same privilege as reading the transcript.
    """
    return get_session_context_action(request=request, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.get("/sessions/{session_id}/plans")
def list_session_plans(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return all stored plans for this session directly from PlanService."""
    return list_session_plans_action(request=request, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.get("/sessions/{session_id}/plans/latest")
def get_latest_session_plan(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return the most recent plan for this session directly from PlanService."""
    return get_latest_session_plan_action(request=request, agent_id=agent_id, session_id=session_id, db=db, guard=guard)

@router.post("/sessions/{session_id}/stream")
async def stream_chat(
    request: Request,
    agent_id: int,
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Run a turn of the agent and stream the result.

    EXECUTE is the consequential privilege in this module. A turn runs tools
    under the agent's own service identity, so granting it delegates whatever
    data that identity can reach — it is never inferred from BROWSE.

    The agent's reach is capped by its owner's at resolution time (see
    ``load_agent_permission_set``), so EXECUTE cannot be used to read through
    an agent what the person responsible for it could not read.
    """
    return await stream_chat_action(request=request, agent_id=agent_id, session_id=session_id, body=body, db=db, guard=guard)
