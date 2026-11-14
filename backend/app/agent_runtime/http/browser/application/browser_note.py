from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

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
