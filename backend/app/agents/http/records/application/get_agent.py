def _bind():
    import app.agents.http.records.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Return an agent's definition.

    BROWSE, not EDIT: the response includes the system prompt, which is what
    someone deciding whether to run this agent needs to read.
    """
    return _agent_response(_load_agent(db, agent_id, guard, Privilege.BROWSE))
