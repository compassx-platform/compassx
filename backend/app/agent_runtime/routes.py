"""FastAPI routes for the Agent Runtime Module."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.agent_runtime.models import (
    AgentChatMessage,
    AgentRuntimeSession,
    CreateAgentSessionRequest,
    SendMessageRequest,
)

from app.agent_runtime.service import agent_runtime_service

import app.agent_runtime.http.sessions.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agent_runtime.http.sessions.application.list_sessions import list_sessions as list_sessions_action
from app.agent_runtime.http.sessions.application.create_session import create_session as create_session_action
from app.agent_runtime.http.sessions.application.get_session import get_session as get_session_action
from app.agent_runtime.http.sessions.application.delete_session import delete_session as delete_session_action
from app.agent_runtime.http.sessions.application.send_message import send_message as send_message_action

router = APIRouter(prefix="/agent-runtime", tags=["agent-runtime"])

@router.get("/sessions", response_model=List[AgentRuntimeSession])
def list_sessions(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List all agent runtime sessions for the workspace."""
    return list_sessions_action(request=request, workspace_id=workspace_id)

@router.post("/sessions", response_model=AgentRuntimeSession, status_code=201)
def create_session(request: Request, body: CreateAgentSessionRequest):
    """Create a new agent runtime session bound to a compute sandbox."""
    return create_session_action(request=request, body=body)

@router.get("/sessions/{session_id}", response_model=AgentRuntimeSession)
def get_session(session_id: str):
    """Get an agent runtime session and its transcript."""
    return get_session_action(session_id=session_id)

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete an agent runtime session."""
    return delete_session_action(session_id=session_id)

@router.post("/sessions/{session_id}/messages", response_model=AgentChatMessage)
def send_message(session_id: str, body: SendMessageRequest):
    """Send a user message to the agent and receive its response."""
    return send_message_action(session_id=session_id, body=body)
