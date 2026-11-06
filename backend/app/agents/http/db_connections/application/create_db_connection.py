def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_db_connection(
    request: Request,
    body: DBConnectionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Register a database connection.

    Storing credentials that anyone granted USE_COMPUTE can then query through
    is an administrative act, so it sits with the workspace admin. The creator
    becomes the owner and can delegate from there.
    """
    guard.require_workspace_admin("Creating a database connection")
    workspace_id = guard.workspace_id
    if body.profiler_agent_id:
        # Profiling runs the named agent against this connection, so the
        # caller must be allowed to run that agent — otherwise setting the
        # field is a way to invoke an agent one cannot otherwise execute.
        authorized_agent(db, guard, body.profiler_agent_id, Privilege.EXECUTE)
    conn = DBConnection(
        workspace_id=workspace_id,
        name=body.name,
        db_type=body.db_type,
        host=body.host,
        port=body.port,
        db_name=body.db_name,
        username_enc=encrypt_field(body.username) if body.username else None,
        password_enc=encrypt_field(body.password) if body.password else None,
        ssl_config=body.ssl_config,
        profiler_agent_id=body.profiler_agent_id,
        scoped_tables=body.scoped_tables,
    )
    sys_db.add(conn)
    sys_db.commit()
    sys_db.refresh(conn)
    guard.claim_ownership(Securable.connection(str(conn.id)))

    # Sync AgentDBConnection
    sync_agent_db_connection(conn.id, conn.profiler_agent_id, conn.scoped_tables, db)

    # Trigger profiling run
    if conn.profiler_agent_id:
        trigger_profiling(conn, str(guard.principal.id), workspace_id, background_tasks)

    return _to_response(conn)
