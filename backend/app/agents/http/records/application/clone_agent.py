def _bind():
    import app.agents.http.records.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def clone_agent(
    request: Request,
    agent_id: int,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Copy an agent into a new one owned by the caller.

    A clone reproduces the source's prompt and tool list verbatim, so it
    discloses exactly what BROWSE does. Creating the copy is still an admin
    action, for the same reason ``create_agent`` is.
    """
    source = _load_agent(db, agent_id, guard, Privilege.BROWSE)
    guard.require_workspace_admin("Cloning an agent")
    workspace_id = guard.workspace_id

    clone = Agent(
        workspace_id=workspace_id,
        llm_connection_id=source.llm_connection_id,
        name=f"{source.name} (copy)",
        description=source.description,
        avatar=source.avatar,
        color=source.color,
        prompt=source.prompt,
        model=source.model,
        max_tokens=source.max_tokens,
        is_orchestrator=source.is_orchestrator,
        visibility=source.visibility,
        status=source.status or "active",
        manifest=source.manifest or {},
        created_by=str(guard.principal.id),
    )
    db.add(clone)
    db.flush()

    for tool in source.tools:
        db.add(AgentTool(agent_id=clone.id, tool_name=tool.tool_name))
    for s in source.skills:
        db.add(AgentSkillAttachment(agent_id=clone.id, skill_id=s.skill_id, position=s.position))

    db.commit()
    # The clone is a new object: it starts with the caller as owner and no
    # grants, rather than inheriting the source's, whose grantees consented to
    # the source and not to a copy someone else now controls.
    guard.claim_ownership(Securable.agent(str(clone.id)))
    return _agent_response(_load_agent(db, clone.id, guard, Privilege.BROWSE))
