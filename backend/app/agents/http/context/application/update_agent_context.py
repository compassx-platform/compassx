def _bind():
    import app.agents.http.context.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_agent_context(
    agent_id: int,
    entry_id: int,
    body: ContextEntryUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    entry = _get_or_404(db, agent_id, entry_id)
    if body.text and body.text != entry.text:
        entry.is_active = False
        new_entry = AgentContextEntry(
            agent_id=agent_id,
            text=body.text,
            tags=body.tags if body.tags is not None else entry.tags,
            version=entry.version + 1,
            is_active=True,
            created_by=str(guard.principal.id),
        )
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        return new_entry
    if body.tags is not None:
        entry.tags = body.tags
    if body.is_active is not None:
        entry.is_active = body.is_active
    db.commit()
    db.refresh(entry)
    return entry
