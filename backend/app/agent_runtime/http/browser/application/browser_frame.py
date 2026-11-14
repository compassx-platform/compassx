from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def browser_frame(session_id: str, tab_id: str = Query(default="browser")):
    """Return the latest pixels of the host-owned browser."""
    data, width, height = _browser_call(agent_runtime_service.browser_frame, session_id, tab_id)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "X-Page-Width": str(width),
            "X-Page-Height": str(height),
            "Cache-Control": "no-store",
        },
    )
