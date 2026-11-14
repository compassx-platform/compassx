from __future__ import annotations

def deliver_prompt(service, session_id: str, content: str, image: str | None = None, llm_model: str | None = None) -> AgentChatMessage:
    """Start the agent tmux session if needed, then type the prompt into it."""
    import app.agent_runtime.service as _origin
    is_nova_agent = _origin.is_nova_agent
    session = service._require_session(session_id)
    prompt = (content or "").strip()
    if not prompt:
        raise ValueError("Message is empty.")
    service._require_running_sandbox(session.sandbox_id)
    if llm_model and llm_model.strip():
        session.llm_model = llm_model.strip()
        service._persist_session_row(session)
    if is_nova_agent(session.agent_type):
        return service._deliver_nova(session, prompt, image=image, llm_model=llm_model)
    service._sync_antigravity_login(session, force=True)
    service._ensure_agent_tmux(session)
    service._wait_for_agent_pane(session)
    service._type_prompt(session, prompt)
    return service._append_message(session, "user", prompt, image=image)
