from __future__ import annotations

def ensure_nova_chat_session(
    db: Session,
    agent: Agent,
    runtime_session_id: str,
    workspace_id: str | None,
    _title: str,
) -> ChatSession:
    import app.agent_runtime.nova as _origin
    runtime_chat_title = _origin.runtime_chat_title
    ChatSession = _origin.ChatSession
    marker = runtime_chat_title(runtime_session_id)
    session = (
        db.query(ChatSession)
        .filter(ChatSession.agent_id == agent.id, ChatSession.title == marker)
        .first()
    )
    if session:
        return session
    session = ChatSession(
        workspace_id=workspace_id,
        agent_id=agent.id,
        title=marker,
        archived=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
