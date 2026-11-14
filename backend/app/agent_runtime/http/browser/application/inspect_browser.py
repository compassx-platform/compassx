from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def inspect_browser(session_id: str, body: BrowserPointRequest):
    """Describe the element under a point in the host-owned browser."""
    return _browser_call(agent_runtime_service.inspect_browser, session_id, body.tab_id, body.x, body.y)
