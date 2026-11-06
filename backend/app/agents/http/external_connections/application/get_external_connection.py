def _bind():
    import app.agents.http.external_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_external_connection(
    connection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    guard: Guard = Depends(get_guard),
):
    return _to_response(_get_or_404(db, connection_id, guard, Privilege.BROWSE))
