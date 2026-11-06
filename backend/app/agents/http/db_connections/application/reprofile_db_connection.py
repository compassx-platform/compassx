def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def reprofile_db_connection(
    request: Request,
    connection_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_account_db),
    sys_db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Re-run the profiler agent against this connection.

    Two privileges, because the run touches two securables: USE_COMPUTE to
    read through the connection, and EXECUTE on the configured agent, which is
    what actually does the reading.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    if not conn.profiler_agent_id:
        raise HTTPException(400, "No profiler agent configured for this connection")
    authorized_agent(sys_db, guard, conn.profiler_agent_id, Privilege.EXECUTE)

    trigger_profiling(conn, str(guard.principal.id), guard.workspace_id, background_tasks)
    return {"status": "queued", "message": "Data profiling run started in the background."}
