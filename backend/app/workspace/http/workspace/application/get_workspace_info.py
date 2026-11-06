from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_workspace_info(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    return {
        "id": ws.id,
        "name": ws.name,
        "slug": ws.slug,
        "status": ws.status,
        "url": f"/w/{ws.slug}",
        "current_user_role": ctx.principal_role,
        "is_account_admin": ctx.is_account_admin,
    }
