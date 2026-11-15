from __future__ import annotations

def sync_terminal_notices(service, session_id: str) -> AgentRuntimeSession:
    """Store terminal errors that are not already in the chat."""
    import app.agent_runtime.service as _origin
    is_nova_agent = _origin.is_nova_agent
    ensure_pane_log_command = _origin.ensure_pane_log_command
    pane_capture_command = _origin.pane_capture_command
    read_pane_log_command = _origin.read_pane_log_command
    agent_registry = _origin.agent_registry
    _notice_already_shown = _origin._notice_already_shown
    session = service._require_session(session_id)
    if is_nova_agent(session.agent_type):
        service._require_running_sandbox(session.sandbox_id)
        from app.agent_runtime.sandbox_controller import nova_sandbox_controller

        service._sync_activities(session, nova_sandbox_controller.read_activities(session, service._exec))
        from app.agent_runtime import tasks as agent_tasks

        agent_tasks.release_finished_session(service, session_id)
        return service._require_session(session_id)
    service._require_running_sandbox(session.sandbox_id)
    service._sync_antigravity_login(session)
    service._exec(session.sandbox_id, ensure_pane_log_command(session.id), timeout=10)
    captured = service._exec(session.sandbox_id, pane_capture_command(session.id, 200), timeout=10)
    logged = service._exec(session.sandbox_id, read_pane_log_command(session.id), timeout=10)
    pane_text = f"{captured.stdout or ''}\n{logged.stdout or ''}"
    adapter = agent_registry.get(session.agent_type)
    # Antigravity already emits thoughts, tool calls, and replies from its transcript.
    # The pane scrape treats status lines such as "2 failed" as errors and copies the reply into them.
    if (session.agent_type or "").lower().strip() in ("antigravity", "agy"):
        service._drop_terminal_errors(session)
        notices = []
    else:
        notices = list(dict.fromkeys(adapter.extract_notices(pane_text) if adapter else []))
    service._collapse_duplicate_notices(session)
    session = service._require_session(session_id)
    service._sync_activities(session, service._read_activities(session, adapter, pane_text))
    session = service._require_session(session_id)
    stored = {
        message.content
        for message in session.messages
        if message.role == "assistant" and (message.kind in (None, "", "error")) and not (message.content or "").startswith("👋")
    }
    for notice in notices:
        if _notice_already_shown(notice, stored):
            continue
        service._append_message(session, "assistant", notice, kind="error")
        stored.add(notice)
    return service._require_session(session_id)
