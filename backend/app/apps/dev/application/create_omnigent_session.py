def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def create_omnigent_session(
    app_id: str,
    body: Optional[CreateSessionRequest] = None,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Create a new conversational AI session on Omnigent Server bound to the app host."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    agent_name = body.agent_name if body else "polly"
    title = body.title if body else None
    try:
        unified_reaper_service.touch_app_activity(app.id)
        unified_reaper_service.touch_omnigent_activity()
        return omnigent_dev_service.create_omnigent_chat_session(app, agent_name=agent_name, title=title)
    except Exception as e:
        logger.exception("Failed to create Omnigent session for app %s: %s", app.name, e)
        raise HTTPException(status_code=500, detail=f"Failed to create Omnigent session: {str(e)}")
