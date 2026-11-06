def _bind():
    import app.agents.http.records.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_agent(
    request: Request,
    body: AgentCreate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Create an agent, owned by its creator.

    An agent holds its own grants and runs tools under its own identity, so
    bringing one into being is an admin action rather than something any
    member may do.
    """
    guard.require_workspace_admin("Creating an agent")
    workspace_id = guard.workspace_id
    agent = Agent(
        workspace_id=workspace_id,
        llm_connection_id=body.llm_connection_id,
        name=body.name,
        description=body.description,
        avatar=body.avatar,
        color=body.color,
        prompt=body.prompt,
        model=body.model,
        max_tokens=body.max_tokens,
        is_orchestrator=body.is_orchestrator,
        visibility=body.visibility,
        status=body.status or "active",
        manifest=body.manifest or {},
        created_by=str(guard.principal.id),
    )
    db.add(agent)
    db.flush()
    _sync_tools(db, agent.id, body.tools)
    _sync_skills(db, agent.id, body.skills)
    db.commit()
    guard.claim_ownership(Securable.agent(str(agent.id)))
    return _agent_response(_load_agent(db, agent.id, guard, Privilege.BROWSE))
