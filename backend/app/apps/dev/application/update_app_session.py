def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def update_app_session(
    app_id: str,
    session_id: str,
    body: UpdateAppSessionRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update an app session's title or status (bound agent is strictly immutable)."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    from app.services.dev_session_service import dev_session_service
    try:
        return dev_session_service.update_session(
            app=app,
            session_id=session_id,
            title=body.title,
            status=body.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
