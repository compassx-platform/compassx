def _bind():
    import app.agents.http.records.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Delete an agent.

    Takes its chat history with it and cannot be undone by whoever was relying
    on it, so MANAGE rather than EDIT.
    """
    agent = _load_agent(db, agent_id, guard, Privilege.MANAGE)
    db.delete(agent)
    db.commit()
