def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_messages(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return a session's transcript.

    Tool output is part of the transcript, so this can contain query results
    the agent read on someone else's behalf — hence a real check rather than
    the bare id lookup that used to be here.
    """
    _get_session_or_404(db, agent_id, session_id, guard, Privilege.BROWSE)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
