def _bind():
    import app.agents.http.llm_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_llm_connection(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    return _to_response(_get_or_404(db, connection_id, guard, Privilege.BROWSE))
