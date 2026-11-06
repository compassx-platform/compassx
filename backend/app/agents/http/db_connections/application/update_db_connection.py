def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_db_connection(
    request: Request,
    connection_id: int,
    body: DBConnectionUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Change a connection's target or credentials.

    EDIT, because this rewrites where the connection points and what it
    authenticates as: everyone already granted USE_COMPUTE on it keeps their
    grant and silently starts querying the new target.
    """
    conn = _get_or_404(sys_db, connection_id, guard, Privilege.EDIT)
    old_profiler_id = conn.profiler_agent_id

    data = body.model_dump(exclude_none=True)
    if data.get("profiler_agent_id") and data["profiler_agent_id"] != old_profiler_id:
        # Same reason as on create: naming an agent here is a way to run it.
        authorized_agent(db, guard, data["profiler_agent_id"], Privilege.EXECUTE)
    if "username" in data:
        conn.username_enc = encrypt_field(data.pop("username"))
    if "password" in data:
        conn.password_enc = encrypt_field(data.pop("password"))
    for field, value in data.items():
        setattr(conn, field, value)
    
    sys_db.commit()
    sys_db.refresh(conn)
    
    # Sync AgentDBConnection
    sync_agent_db_connection(conn.id, conn.profiler_agent_id, conn.scoped_tables or [], db)
    
    # Trigger profiling if profiler_agent_id changed/updated
    if conn.profiler_agent_id and conn.profiler_agent_id != old_profiler_id:
        trigger_profiling(conn, str(guard.principal.id), guard.workspace_id, background_tasks)

    return _to_response(conn)
