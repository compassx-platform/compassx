def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def create_app_session(
    app_id: str,
    body: CreateAppSessionRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new development session with a permanently bound agent."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    unified_reaper_service.touch_app_activity(app.id)
    user_id = str(guard.principal.id) if hasattr(guard, "principal") and getattr(guard.principal, "id", None) else None
    from app.services.dev_session_service import dev_session_service
    return dev_session_service.create_session(
        app=app,
        agent=body.agent,
        title=body.title,
        workspace_id=body.workspace_id,
        user_id=user_id,
        model=body.model,
    )
