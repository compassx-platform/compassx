def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_session(
    request: Request,
    agent_id: int,
    body: ChatSessionCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Open a conversation with an agent.

    EXECUTE, matching ``stream_chat``: a session exists to be run, and a
    principal who may not run the agent has no use for an empty one.
    """
    _get_agent_or_404(db, agent_id, guard, Privilege.EXECUTE)
    session = ChatSession(
        workspace_id=guard.workspace_id, agent_id=agent_id, title=body.title
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session
