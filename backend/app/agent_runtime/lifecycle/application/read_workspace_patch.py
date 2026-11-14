from __future__ import annotations

def read_workspace_patch(service, session_id: str) -> DiffResponse:
    import app.agent_runtime.service as _origin
    patch_command = _origin.patch_command
    DiffResponse = _origin.DiffResponse
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    payload = service._exec_json(session.sandbox_id, patch_command(), timeout=30)
    return DiffResponse(path="", diff=str(payload.get("diff") or ""))
