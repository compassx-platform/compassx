from __future__ import annotations

def send_message(service, session_id: str, content: str) -> AgentChatMessage:
    """Deliver a follow-up prompt into the session's tmux agent."""
    return service.deliver_prompt(session_id, content)
