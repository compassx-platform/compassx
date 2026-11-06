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
