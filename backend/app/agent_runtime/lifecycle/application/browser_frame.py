from __future__ import annotations

def browser_frame(service, session_id: str, tab_id: str) -> tuple[bytes, int, int]:
    from app.agent_runtime.browser_host import browser_host

    return browser_host.frame(service._browser_key(session_id, tab_id))
