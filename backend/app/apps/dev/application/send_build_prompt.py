def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def send_build_prompt(
    app_id: str,
    body: BuildPromptRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Send an AI coding instruction / prompt to the Build Studio session."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    if not body.prompt or not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    unified_reaper_service.touch_app_activity(app.id)
    _sync_agent_login(app, force=True)
    session_id = body.session_id
    if not session_id:
        sess = omnigent_dev_service.get_build_session(app, workspace_id=body.workspace_id)
        session_id = sess.get("session_id")

    result = omnigent_dev_service.send_build_session_prompt(
        app,
        session_id=session_id,
        prompt=body.prompt.strip(),
        agent_name=body.agent_name,
        workspace_id=body.workspace_id,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=409, detail=result.get("message") or "Agent terminal is not ready.")
    return result
