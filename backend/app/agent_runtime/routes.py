"""FastAPI routes for the Agent Runtime Module."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
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

import app.agent_runtime.http.sessions.prelude as _prelude
for _name, _value in vars(_prelude).items():
    if not _name.startswith('__'):
        globals()[_name] = _value

from app.agent_runtime.http.sessions.application.list_sessions import list_sessions as list_sessions_action
from app.agent_runtime.http.sessions.application.create_session import create_session as create_session_action
from app.agent_runtime.http.sessions.application.get_session import get_session as get_session_action
from app.agent_runtime.http.sessions.application.delete_session import delete_session as delete_session_action

router = APIRouter(prefix="/agent-runtime", tags=["agent-runtime"])

@router.post("/sandbox/tools")
async def sandbox_platform_tool(request: Request):
    """Execute a CompassX platform tool on behalf of Nova running in a sandbox."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    from app.agent_runtime.sandbox_tools import execute_platform_tool

    try:
        return await execute_platform_tool(request, body if isinstance(body, dict) else {})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:400])


@router.get("/agents", response_model=List[AgentCatalogItem])
def list_agents():
    """Agents the runtime can launch. New agents appear here when they are registered."""
    from app.sandbox.agents import agent_registry

    return agent_registry.catalog()


@router.get("/projects", response_model=List[AgentRuntimeProject])
def list_projects(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List agent runtime projects for the workspace."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = workspace_id or (str(ctx.workspace_id) if ctx else None)
    return agent_runtime_service.list_projects(workspace_id=ws_id)


@router.post("/projects", response_model=AgentRuntimeProject, status_code=201)
def create_project(request: Request, body: CreateProjectRequest):
    """Create a project that sessions can be added to."""
    ctx = getattr(request.state, "workspace", None)
    ws_id = str(ctx.workspace_id) if ctx else None
    try:
        return agent_runtime_service.create_project(body, workspace_id=ws_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(exc)}")


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """Delete a project. Its sessions stay, without a project."""
    ok = agent_runtime_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return {"deleted": True, "project_id": project_id}


@router.get("/sessions", response_model=List[AgentRuntimeSession])
def list_sessions(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List all agent runtime sessions for the workspace."""
    return list_sessions_action(request=request, workspace_id=workspace_id)

@router.get("/sandboxes/{sandbox_id}/git", response_model=GitInfoResponse)
def sandbox_git(sandbox_id: str):
    """Current branch and local branches for a running sandbox workspace."""
    try:
        return agent_runtime_service.sandbox_git(sandbox_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read git branches: {str(exc)}")


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


@router.post("/sessions/{session_id}/start", response_model=AgentChatMessage)
def start_session(session_id: str, body: SendMessageRequest):
    """Start the selected agent in tmux and deliver the first prompt."""
    return _run_prompt(session_id, body.content, llm_model=body.llm_model)


@router.post("/sessions/{session_id}/notices/sync", response_model=AgentRuntimeSession)
def sync_notices(session_id: str):
    """Copy new terminal errors into the chat transcript."""
    try:
        return agent_runtime_service.sync_terminal_notices(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to capture terminal errors: {str(exc)}")


@router.post("/sessions/{session_id}/messages", response_model=AgentChatMessage)
def send_message(session_id: str, body: SendMessageRequest):
    """Send a follow-up prompt into the running tmux agent."""
    return _run_prompt(session_id, body.content, llm_model=body.llm_model)


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


@router.post("/sessions/{session_id}/browser/open")
def open_browser(session_id: str, body: BrowserOpenRequest):
    """Open a URL in the host-owned browser for this session tab."""
    return _browser_call(agent_runtime_service.open_browser, session_id, body.tab_id, body.url, body.width, body.height)


@router.get("/sessions/{session_id}/browser/frame")
def browser_frame(session_id: str, tab_id: str = Query(default="browser")):
    """Return the latest pixels of the host-owned browser."""
    data, width, height = _browser_call(agent_runtime_service.browser_frame, session_id, tab_id)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "X-Page-Width": str(width),
            "X-Page-Height": str(height),
            "Cache-Control": "no-store",
        },
    )


@router.post("/sessions/{session_id}/browser/inspect", response_model=BrowserTargetResponse)
def inspect_browser(session_id: str, body: BrowserPointRequest):
    """Describe the element under a point in the host-owned browser."""
    return _browser_call(agent_runtime_service.inspect_browser, session_id, body.tab_id, body.x, body.y)


@router.post("/sessions/{session_id}/browser/input")
def browser_input(session_id: str, body: BrowserInputRequest):
    """Forward a click, key, or scroll to the host-owned browser."""
    _browser_call(
        agent_runtime_service.browser_input,
        session_id,
        body.tab_id,
        body.kind,
        body.x,
        body.y,
        body.delta_y,
        body.key,
        body.text,
    )
    return {"ok": True}


@router.post("/sessions/{session_id}/browser/note", response_model=AgentChatMessage)
def browser_note(session_id: str, body: BrowserNoteRequest):
    """Send an annotation note and its cropped screenshot to the agent."""
    return _browser_call(
        agent_runtime_service.send_browser_note,
        session_id,
        body.tab_id,
        body.instruction,
        body.x,
        body.y,
        body.width,
        body.height,
    )


@router.get("/sessions/{session_id}/output", response_model=AgentOutputResponse)
def read_output(session_id: str):
    """Return the live agent pane so chat stays in sync with the terminal."""
    try:
        return AgentOutputResponse(output=agent_runtime_service.capture_agent_output(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read agent output: {str(exc)}")


@router.get("/sessions/{session_id}/files", response_model=WorkspaceFilesResponse)
def list_files(session_id: str):
    """List files and directories in the session sandbox workspace."""
    return _workspace_call(agent_runtime_service.list_workspace_files, session_id)


@router.get("/sessions/{session_id}/files/content", response_model=FileContentResponse)
def read_file(session_id: str, path: str = Query(...)):
    """Read one workspace file."""
    return _workspace_call(agent_runtime_service.read_workspace_file, session_id, path)


@router.put("/sessions/{session_id}/files/content", response_model=WriteFileResponse)
def write_file(session_id: str, body: WriteFileRequest):
    """Write one workspace file from the editor."""
    return _workspace_call(agent_runtime_service.write_workspace_file, session_id, body.path, body.content)


@router.get("/sessions/{session_id}/changes", response_model=ChangesResponse)
def list_changes(session_id: str):
    """List git changes in the session sandbox workspace."""
    return _workspace_call(agent_runtime_service.list_workspace_changes, session_id)


@router.get("/sessions/{session_id}/changes/patch", response_model=DiffResponse)
def read_patch(session_id: str):
    """Return one diff of every uncommitted workspace change."""
    return _workspace_call(agent_runtime_service.read_workspace_patch, session_id)


@router.get("/sessions/{session_id}/changes/diff", response_model=DiffResponse)
def read_diff(session_id: str, path: str = Query(...)):
    """Return the unified diff for one workspace path."""
    return _workspace_call(agent_runtime_service.read_workspace_diff, session_id, path)


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
