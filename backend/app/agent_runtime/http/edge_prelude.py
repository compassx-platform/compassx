"""Names the agent-runtime HTTP actions close over.

Logger text and status codes stay in the action that writes them.
"""
from typing import List, Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import Response

from app.agent_runtime.models import (
    AgentChatMessage,
    AgentRuntimeProject,
    AgentRuntimeSession,
    ChangesResponse,
    CreateAgentSessionRequest,
    GitInfoResponse,
    CreateProjectRequest,
    DiffResponse,
    AgentCatalogItem,
    AgentOutputResponse,
    FileContentResponse,
    BrowserInputRequest,
    BrowserNoteRequest,
    BrowserOpenRequest,
    BrowserPointRequest,
    BrowserTargetResponse,
    SendMessageRequest,
    WriteFileRequest,
    WriteFileResponse,
    WorkspaceFilesResponse,
)
from app.agent_runtime.service import agent_runtime_service

def _run_prompt(session_id: str, content: str, llm_model: str | None = None) -> AgentChatMessage:
    try:
        return agent_runtime_service.deliver_prompt(session_id, content, llm_model=llm_model)
    except ValueError as exc:
        status = 400 if "empty" in str(exc).lower() else 404
        raise HTTPException(status_code=status, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(exc)}")


def _browser_call(fn, *args):
    try:
        return fn(*args)
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Browser host failed: {str(exc)}")


def _workspace_call(fn, session_id: str, *args):
    try:
        return fn(session_id, *args)
    except ValueError as exc:
        status = 400 if "path" in str(exc).lower() or "empty" in str(exc).lower() else 404
        raise HTTPException(status_code=status, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read workspace: {str(exc)}")

