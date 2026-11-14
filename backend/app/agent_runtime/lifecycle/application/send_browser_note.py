from __future__ import annotations

def send_browser_note(service, session_id: str, tab_id: str, instruction: str, x: float, y: float, width: float, height: float) -> AgentChatMessage:
    """Capture the host browser and deliver the note plus screenshot to the agent."""
    import app.agent_runtime.service as _origin
    logger = _origin.logger
    base64 = _origin.base64
    from app.agent_runtime.browser_host import browser_host

    note = (instruction or "").strip()
    if not note:
        raise ValueError("Message is empty.")
    shot, target = browser_host.capture(service._browser_key(session_id, tab_id), x, y, width, height)
    session = service._require_session(session_id)
    path = ""
    try:
        path = service._save_note_image(session.sandbox_id, shot)
    except Exception as exc:
        logger.warning("[AgentRuntimeService] Could not store the annotation screenshot: %s", exc)
    prompt = f"Browser annotation\n{target['detail']}\n\n{note}"
    if path:
        prompt += f"\n\nScreenshot file: {path}\nRead that screenshot file before changing the page."
    image = "data:image/jpeg;base64," + base64.b64encode(shot).decode("ascii")
    return service.deliver_prompt(session_id, prompt, image=image)
