def _bind():
    import app.agents.http.tool_execution.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def execute_tool_endpoint(
    payload: AgentToolExecuteRequest,
    request: Request,
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Execute a promoted catalog tool in an isolated ephemeral execution pod."""
    tool = _authorized_tool(account_db, guard, payload.tool_id)
    if payload.connection_id:
        authorized_connection(
            system_db, guard, ExternalConnection, payload.connection_id, Privilege.USE_COMPUTE
        )

    res = await execute_agent_tool(
        # The resolved id, not the caller's string: the executor would
        # otherwise redo the name lookup and could land on a different row.
        tool_id=tool.id,
        version=payload.version,
        connection_id=payload.connection_id,
        params=payload.params or {},
        session_id=payload.session_id,
        agent_type=payload.agent_type or "nova",
        invoked_by=str(guard.principal.id),
    )
    return AgentToolExecuteResponse(**res)
