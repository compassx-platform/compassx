def _bind():
    import app.apps.dev.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def exec_dev_command(
    app_id: str,
    body: ExecCommandRequest,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Execute a single shell command inside the dev sandbox container."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot access app in another workspace.")
    if not body.command or not body.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty.")

    unified_reaper_service.touch_app_activity(app.id)
    return dev_terminal_service.exec_command(
        app,
        command=body.command.strip(),
        workspace_id=body.workspace_id,
        workspace_name=body.workspace_name,
    )
