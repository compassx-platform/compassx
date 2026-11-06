def _bind():
    import app.apps.record.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith('__'):
            target[key] = value

_bind()

def update_app(
    app_id: str,
    body: AppUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    """Update an application."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")

    if guard.workspace_id and app.workspace_id != guard.workspace_id:
        raise HTTPException(status_code=403, detail="Cannot modify app from another workspace.")

    if body.name is not None:
        app.name = body.name
    if body.description is not None:
        app.description = body.description
    if body.app_type is not None:
        app.app_type = body.app_type
    if body.status is not None:
        app.status = body.status
    if body.route is not None:
        app.route = body.route
    if body.git_provider is not None:
        app.git_provider = body.git_provider
    if body.git_repo_url is not None:
        app.git_repo_url = body.git_repo_url
    if body.git_ref is not None:
        app.git_ref = body.git_ref
        app.git_branch = body.git_ref
    if body.git_ref_type is not None:
        app.git_ref_type = body.git_ref_type
    if body.git_subdir is not None:
        app.git_subdir = body.git_subdir
    if body.entrypoint is not None:
        app.entrypoint = body.entrypoint
    if body.git_credential_type is not None:
        app.git_credential_type = body.git_credential_type
    if body.git_credential_nickname is not None:
        app.git_credential_nickname = body.git_credential_nickname
    if body.git_connection_id is not None:
        app.git_connection_id = body.git_connection_id
    if body.git_pat is not None:
        app.git_pat_enc = encrypt_field(body.git_pat) if body.git_pat else None
    if body.config is not None:
        app.config = body.config
        flag_modified(app, "config")

    db.commit()
    db.refresh(app)
    return _to_response(app)
