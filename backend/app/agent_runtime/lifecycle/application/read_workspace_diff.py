from __future__ import annotations

def read_workspace_diff(service, session_id: str, path: str) -> DiffResponse:
    import app.agent_runtime.service as _origin
    safe_relative_path = _origin.safe_relative_path
    diff_command = _origin.diff_command
    DiffResponse = _origin.DiffResponse
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    relative = safe_relative_path(path)
    payload = service._exec_json(session.sandbox_id, diff_command(relative), timeout=30)
    return DiffResponse(path=str(payload.get("path") or relative), diff=str(payload.get("diff") or ""))
