def _bind():
    import app.agents.http.context.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_agent_context(
    agent_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    authorized_agent(db, guard, agent_id, Privilege.EDIT)
    entry = _get_or_404(db, agent_id, entry_id)
    db.delete(entry)
    db.commit()
