from __future__ import annotations

def capture_agent_output(service, session_id: str) -> str:
    """Read the live agent pane so the chat view stays aligned with the terminal."""
    import app.agent_runtime.service as _origin
    pane_capture_command = _origin.pane_capture_command
    session = service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    result = service._exec(session.sandbox_id, pane_capture_command(session.id), timeout=10)
    return result.stdout or ""
