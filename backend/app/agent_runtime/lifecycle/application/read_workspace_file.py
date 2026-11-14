from __future__ import annotations

def read_workspace_file(service, session_id: str, path: str) -> FileContentResponse:
    import app.agent_runtime.service as _origin
    safe_relative_path = _origin.safe_relative_path
    file_content_command = _origin.file_content_command
    FileContentResponse = _origin.FileContentResponse
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    relative = safe_relative_path(path)
    payload = service._exec_json(session.sandbox_id, file_content_command(relative), timeout=20)
    return FileContentResponse(
        path=str(payload.get("path") or relative),
        content=str(payload.get("content") or ""),
        truncated=bool(payload.get("truncated")),
        missing=bool(payload.get("missing")),
    )
