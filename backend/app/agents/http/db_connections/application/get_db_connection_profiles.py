def _bind():
    import app.agents.http.db_connections.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_db_connection_profiles(
    request: Request,
    connection_id: int,
    db: Session = Depends(get_db),
    sys_db: Session = Depends(get_account_db),
    guard: Guard = Depends(get_guard),
):
    """Return the stored profiles for a connection.

    BROWSE: these are CompassX's own notes about the source — column stats and
    inferred relationships — not a live read of it.
    """
    _get_or_404(sys_db, connection_id, guard, Privilege.BROWSE)
    profiles = db.query(DataSourceProfile).filter(DataSourceProfile.connection_id == connection_id).all()
    return [DataSourceProfileResponse.model_validate(p) for p in profiles]
