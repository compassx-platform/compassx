def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def clear_build_session(
    app_id: str,
    body: Optional[BuildClearRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Clear Build Studio session history and start fresh conversation."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    ws_id = body.workspace_id if body else None
    session_id = body.session_id if body else None
    unified_reaper_service.touch_app_activity(app.id)
    return omnigent_dev_service.clear_build_session(app, workspace_id=ws_id, session_id=session_id)
