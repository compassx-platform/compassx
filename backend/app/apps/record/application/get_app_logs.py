def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def get_app_logs(
    app_id: str,
    tail: int = Query(250, description="Number of tail lines to retrieve"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Retrieve actual live runtime container / process logs for an application."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    live_logs = app_runner_service.get_live_logs(app, tail=tail)

    return AppLogsResponse(
        app_id=app.id,
        status=app.status,
        logs=live_logs,
    )
