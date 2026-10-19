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

router = APIRouter(prefix="/agent-runtime", tags=["agent-runtime"])


@router.get("/sessions", response_model=List[AgentRuntimeSession])
def list_sessions(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List all agent runtime sessions for the workspace."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = workspace_id or (str(ctx.workspace_id) if ctx else None)
    return agent_runtime_service.list_sessions(workspace_id=ws_id)



@router.post("/sessions", response_model=AgentRuntimeSession, status_code=201)
def create_session(request: Request, body: CreateAgentSessionRequest):
    """Create a new agent runtime session bound to a compute sandbox."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = str(ctx.workspace_id) if ctx else None
    try:
        return agent_runtime_service.create_session(body, workspace_id=ws_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions/{session_id}", response_model=AgentRuntimeSession)
def get_session(session_id: str):
    """Get an agent runtime session and its transcript."""
    sess = agent_runtime_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return sess


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete an agent runtime session."""
    ok = agent_runtime_service.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"deleted": True, "session_id": session_id}


@router.post("/sessions/{session_id}/messages", response_model=AgentChatMessage)
def send_message(session_id: str, body: SendMessageRequest):
    """Send a user message to the agent and receive its response."""
    try:
        return agent_runtime_service.send_message(session_id, body.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")
