from __future__ import annotations

def inspect_browser(service, session_id: str, tab_id: str, x: float, y: float) -> dict:
    from app.agent_runtime.browser_host import browser_host

    return browser_host.inspect(service._browser_key(session_id, tab_id), x, y)
