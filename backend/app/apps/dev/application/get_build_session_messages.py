def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def get_build_session_messages(
    app_id: str,
    session_id: str = Query(...),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Get chat transcript items for the specified Build Studio session."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    _sync_agent_login(app)
    return omnigent_dev_service.get_build_session_messages(app, session_id=session_id)
