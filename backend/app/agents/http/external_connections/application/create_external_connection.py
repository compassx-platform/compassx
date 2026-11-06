def _bind():
    import app.agents.http.external_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_external_connection(
    payload: ExternalConnectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    """Register an external system.

    Admin: ``auth_config`` is a credential for a system CompassX does not
    control, and every agent granted on the connection then calls with it.
    """
    guard.require_workspace_admin("Creating an external connection")
    try:
        conn = svc.create_connection(
            db=db,
            data=payload,
            workspace_id=guard.workspace_id,
            user_id=str(guard.principal.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    guard.claim_ownership(Securable.connection(str(conn.id)))
    return _to_response(conn)
