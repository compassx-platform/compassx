from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def open_browser(session_id: str, body: BrowserOpenRequest):
    """Open a URL in the host-owned browser for this session tab."""
    return _browser_call(agent_runtime_service.open_browser, session_id, body.tab_id, body.url, body.width, body.height)
