def _bind():
    import app.agents.http.context.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_agent_context(
    agent_id: int,
    active_only: bool = True,
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List an agent's standing context entries."""
    authorized_agent(db, guard, agent_id, Privilege.BROWSE)
    q = db.query(AgentContextEntry).filter(AgentContextEntry.agent_id == agent_id)
    if active_only:
        q = q.filter(AgentContextEntry.is_active.is_(True))
    if search:
        q = q.filter(AgentContextEntry.text.ilike(f"%{search}%"))
    return q.order_by(AgentContextEntry.created_at.desc()).all()
