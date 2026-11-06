def _bind():
    import app.agents.http.chat.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def archive_session(
    request: Request,
    agent_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Archive a session, hiding it from the session list.

    EXECUTE: sessions are shared per agent, so whoever may run the agent may
    tidy up the conversations on it. The history is retained, not deleted.
    """
    session = _get_session_or_404(db, agent_id, session_id, guard, Privilege.EXECUTE)
    session.archived = True
    db.commit()
