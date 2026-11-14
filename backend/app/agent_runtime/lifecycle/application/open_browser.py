from __future__ import annotations

def open_browser(service, session_id: str, tab_id: str, url: str, width: int, height: int) -> dict:
    from app.agent_runtime.browser_host import browser_host

    return browser_host.open(service._browser_key(session_id, tab_id), url, width, height)
