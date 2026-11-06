def _bind():
    import app.agents.http.context.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def add_agent_context(
    agent_id: int,
    body: ContextEntryCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Add a standing instruction to an agent.

    EDIT, because this text is prepended to every subsequent run: it changes
    what the agent does for everyone who may execute it.
    """
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    entry = AgentContextEntry(
        agent_id=agent_id,
        text=body.text,
        tags=body.tags,
        created_by=str(guard.principal.id),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
