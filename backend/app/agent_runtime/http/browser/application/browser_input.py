from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

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
