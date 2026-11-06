from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_workspace_settings(
    slug: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    cfg = dict(ws.storage_config or {})
    existing = cfg.get("workspace_settings") or {}
    
    # Merge updates into existing settings
    for key, value in body.items():
        if isinstance(value, dict) and key in existing and isinstance(existing[key], dict):
            existing[key] = {**existing[key], **value}
        else:
            existing[key] = value

    cfg["workspace_settings"] = existing
    ws.storage_config = cfg
    db.commit()
    db.refresh(ws)

    # Return full merged settings
    merged = {**DEFAULT_WORKSPACE_SETTINGS, **existing}
    for k in ["package_repositories", "base_environments", "serverless_usage_policies", "classic_compute_policies"]:
        if k in DEFAULT_WORKSPACE_SETTINGS and isinstance(DEFAULT_WORKSPACE_SETTINGS[k], dict):
            merged[k] = {**DEFAULT_WORKSPACE_SETTINGS[k], **existing.get(k, {})}

    return merged
