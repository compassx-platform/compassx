"""FastAPI routes for the Agent Runtime Module."""

from typing import List, Optional

from fastapi import APIRouter, Query, Request

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
    from app.agent_runtime.http.sandbox.application.sandbox_platform_tool import sandbox_platform_tool as sandbox_platform_tool_action
    return await sandbox_platform_tool_action(request)


@router.get("/agents", response_model=List[AgentCatalogItem])
def list_agents():
    """Agents the runtime can launch. New agents appear here when they are registered."""
    from app.agent_runtime.http.agents.application.list_agents import list_agents as list_agents_action
    return list_agents_action()


@router.get("/projects", response_model=List[AgentRuntimeProject])
def list_projects(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List agent runtime projects for the workspace."""
    from app.agent_runtime.http.projects.application.list_projects import list_projects as list_projects_action
    return list_projects_action(request, workspace_id)


@router.post("/projects", response_model=AgentRuntimeProject, status_code=201)
def create_project(request: Request, body: CreateProjectRequest):
    """Create a project that sessions can be added to."""
    from app.agent_runtime.http.projects.application.create_project import create_project as create_project_action
    return create_project_action(request, body)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """Delete a project. Its sessions stay, without a project."""
    from app.agent_runtime.http.projects.application.delete_project import delete_project as delete_project_action
    return delete_project_action(project_id)


@router.get("/sessions", response_model=List[AgentRuntimeSession])
def list_sessions(request: Request, workspace_id: Optional[str] = Query(default=None)):
    """List all agent runtime sessions for the workspace."""
    return list_sessions_action(request=request, workspace_id=workspace_id)

@router.get("/sandboxes/{sandbox_id}/git", response_model=GitInfoResponse)
def sandbox_git(sandbox_id: str):
    """Current branch and local branches for a running sandbox workspace."""
    from app.agent_runtime.http.sandbox.application.sandbox_git import sandbox_git as sandbox_git_action
    return sandbox_git_action(sandbox_id)


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



@router.post("/sessions/{session_id}/start", response_model=AgentChatMessage)
def start_session(session_id: str, body: SendMessageRequest):
    """Start the selected agent in tmux and deliver the first prompt."""
    from app.agent_runtime.http.sessions.application.start_session import start_session as start_session_action
    return start_session_action(session_id, body)


@router.post("/sessions/{session_id}/notices/sync", response_model=AgentRuntimeSession)
def sync_notices(session_id: str):
    """Copy new terminal errors into the chat transcript."""
    from app.agent_runtime.http.sessions.application.sync_notices import sync_notices as sync_notices_action
    return sync_notices_action(session_id)


@router.post("/sessions/{session_id}/messages", response_model=AgentChatMessage)
def send_message(session_id: str, body: SendMessageRequest):
    """Send a follow-up prompt into the running tmux agent."""
    from app.agent_runtime.http.sessions.application.send_message import send_message as send_message_action
    return send_message_action(session_id, body)




@router.post("/sessions/{session_id}/browser/open")
def open_browser(session_id: str, body: BrowserOpenRequest):
    """Open a URL in the host-owned browser for this session tab."""
    from app.agent_runtime.http.browser.application.open_browser import open_browser as open_browser_action
    return open_browser_action(session_id, body)


@router.get("/sessions/{session_id}/browser/frame")
def browser_frame(session_id: str, tab_id: str = Query(default="browser")):
    """Return the latest pixels of the host-owned browser."""
    from app.agent_runtime.http.browser.application.browser_frame import browser_frame as browser_frame_action
    return browser_frame_action(session_id, tab_id)


@router.post("/sessions/{session_id}/browser/inspect", response_model=BrowserTargetResponse)
def inspect_browser(session_id: str, body: BrowserPointRequest):
    """Describe the element under a point in the host-owned browser."""
    from app.agent_runtime.http.browser.application.inspect_browser import inspect_browser as inspect_browser_action
    return inspect_browser_action(session_id, body)


@router.post("/sessions/{session_id}/browser/input")
def browser_input(session_id: str, body: BrowserInputRequest):
    """Forward a click, key, or scroll to the host-owned browser."""
    from app.agent_runtime.http.browser.application.browser_input import browser_input as browser_input_action
    return browser_input_action(session_id, body)


@router.post("/sessions/{session_id}/browser/note", response_model=AgentChatMessage)
def browser_note(session_id: str, body: BrowserNoteRequest):
    """Send an annotation note and its cropped screenshot to the agent."""
    from app.agent_runtime.http.browser.application.browser_note import browser_note as browser_note_action
    return browser_note_action(session_id, body)


@router.get("/sessions/{session_id}/output", response_model=AgentOutputResponse)
def read_output(session_id: str):
    """Return the live agent pane so chat stays in sync with the terminal."""
    from app.agent_runtime.http.sessions.application.read_output import read_output as read_output_action
    return read_output_action(session_id)


@router.get("/sessions/{session_id}/files", response_model=WorkspaceFilesResponse)
def list_files(session_id: str):
    """List files and directories in the session sandbox workspace."""
    from app.agent_runtime.http.workspace.application.list_files import list_files as list_files_action
    return list_files_action(session_id)


@router.get("/sessions/{session_id}/files/content", response_model=FileContentResponse)
def read_file(session_id: str, path: str = Query(...)):
    """Read one workspace file."""
    from app.agent_runtime.http.workspace.application.read_file import read_file as read_file_action
    return read_file_action(session_id, path)


@router.put("/sessions/{session_id}/files/content", response_model=WriteFileResponse)
def write_file(session_id: str, body: WriteFileRequest):
    """Write one workspace file from the editor."""
    from app.agent_runtime.http.workspace.application.write_file import write_file as write_file_action
    return write_file_action(session_id, body)


@router.get("/sessions/{session_id}/changes", response_model=ChangesResponse)
def list_changes(session_id: str):
    """List git changes in the session sandbox workspace."""
    from app.agent_runtime.http.workspace.application.list_changes import list_changes as list_changes_action
    return list_changes_action(session_id)


@router.get("/sessions/{session_id}/changes/patch", response_model=DiffResponse)
def read_patch(session_id: str):
    """Return one diff of every uncommitted workspace change."""
    from app.agent_runtime.http.workspace.application.read_patch import read_patch as read_patch_action
    return read_patch_action(session_id)


@router.get("/sessions/{session_id}/changes/diff", response_model=DiffResponse)
def read_diff(session_id: str, path: str = Query(...)):
    """Return the unified diff for one workspace path."""
    from app.agent_runtime.http.workspace.application.read_diff import read_diff as read_diff_action
    return read_diff_action(session_id, path)


