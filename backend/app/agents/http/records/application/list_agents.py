def _bind():
    import app.agents.http.records.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_agents(
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """List the agents in this workspace that the caller may browse."""
    agents = (
        db.query(Agent)
        .filter(Agent.workspace_id == guard.workspace_id)
        .options(selectinload(Agent.tools))
        .order_by(Agent.name)
        .all()
    )
    agents = visible_agents(guard, agents)
    return [
        AgentListResponse(
            id=a.id,
            llm_connection_id=a.llm_connection_id,
            name=a.name,
            description=a.description,
            avatar=a.avatar,
            color=a.color,
            model=a.model,
            is_orchestrator=a.is_orchestrator,
            visibility=a.visibility,
            is_active=a.is_active,
            tool_count=len(a.tools),
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in agents
    ]
