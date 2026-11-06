def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def list_apps(
    request: Request,
    workspace_id: Optional[str] = Query(None),
    workspace_slug: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """List all applications belonging to the caller's workspace."""
    target_ws = workspace_id or guard.workspace_id
    query = db.query(App)

    if target_ws:
        query = query.filter(App.workspace_id == target_ws)
    elif workspace_slug:
        query = query.filter(App.workspace_slug == workspace_slug)

    apps = query.order_by(App.created_at.desc()).all()
    return [_to_response(a) for a in apps]
