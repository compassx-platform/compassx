from __future__ import annotations

def browser_input(service, session_id: str, tab_id: str, kind: str, x: float, y: float, delta_y: float, key_name: str, text: str) -> None:
    from app.agent_runtime.browser_host import browser_host

    browser_host.input(service._browser_key(session_id, tab_id), kind, x, y, delta_y, key_name, text)
