def _bind():
    import app.agents.http.records.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_agent(
    request: Request,
    agent_id: int,
    body: AgentUpdate,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Change an agent's definition.

    EDIT covers the prompt, model, and tool list — that is, what the agent
    does and what it may reach. Anyone who can run the agent inherits the
    consequences, so it is deliberately not implied by EXECUTE.
    """
    agent = _load_agent(db, agent_id, guard, Privilege.EDIT)
    data = body.model_dump(exclude_none=True)
    tools = data.pop("tools", None)
    data.pop("db_connections", None)
    data.pop("git_connections", None)
    skills = data.pop("skills", None)
    for field, value in data.items():
        setattr(agent, field, value)
    if tools is not None:
        db.query(AgentTool).filter(AgentTool.agent_id == agent_id).delete()
        _sync_tools(db, agent_id, tools)
    if skills is not None:
        db.query(AgentSkillAttachment).filter(AgentSkillAttachment.agent_id == agent_id).delete()
        _sync_skills(db, agent_id, skills)
    db.commit()
    return _agent_response(_load_agent(db, agent_id, guard, Privilege.BROWSE))
