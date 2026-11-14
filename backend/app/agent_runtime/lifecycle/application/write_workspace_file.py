from __future__ import annotations

def write_workspace_file(service, session_id: str, path: str, content: str) -> WriteFileResponse:
    import app.agent_runtime.service as _origin
    safe_relative_path = _origin.safe_relative_path
    write_file_command = _origin.write_file_command
    WriteFileResponse = _origin.WriteFileResponse
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    relative = safe_relative_path(path)
    payload = service._exec_json(session.sandbox_id, write_file_command(relative, content or ""), timeout=30)
    return WriteFileResponse(path=str(payload.get("path") or relative), bytes=int(payload.get("bytes") or 0))
