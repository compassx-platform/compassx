from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_workspace_settings(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    cfg = dict(ws.storage_config or {})
    saved_settings = cfg.get("workspace_settings") or {}
    
    # Deep merge with defaults
    merged = {**DEFAULT_WORKSPACE_SETTINGS, **saved_settings}
    for k in ["package_repositories", "base_environments", "serverless_usage_policies", "classic_compute_policies"]:
        if k in DEFAULT_WORKSPACE_SETTINGS and isinstance(DEFAULT_WORKSPACE_SETTINGS[k], dict):
            merged[k] = {**DEFAULT_WORKSPACE_SETTINGS[k], **saved_settings.get(k, {})}

    return merged
