def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


async def ping_llm_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Send a probe request to the provider.

    USE_COMPUTE: it spends the stored key on a real API call, so it takes the
    privilege that calling through the connection takes.
    """
    conn = _get_or_404(db, connection_id, guard, Privilege.USE_COMPUTE)
    success, error = await llm_ping(conn)
    return PingResponse(success=success, message="Connection successful" if success else f"Connection failed: {error}")
