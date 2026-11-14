from __future__ import annotations

def list_workspace_files(service, session_id: str) -> WorkspaceFilesResponse:
    import app.agent_runtime.service as _origin
    files_command = _origin.files_command
    WorkspaceEntry = _origin.WorkspaceEntry
    WorkspaceFilesResponse = _origin.WorkspaceFilesResponse
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    payload = service._exec_json(session.sandbox_id, files_command(), timeout=30)
    entries = [
        WorkspaceEntry(
            path=str(item.get("path") or ""),
            type=str(item.get("type") or "file"),
            size=int(item.get("size") or 0),
        )
        for item in payload.get("entries") or []
        if item.get("path")
    ]
    return WorkspaceFilesResponse(root=str(payload.get("root") or "/workspace"), entries=entries)
