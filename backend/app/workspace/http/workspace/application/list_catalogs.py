from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_catalogs(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    catalogs = db.query(WorkspaceCatalog).filter(
        WorkspaceCatalog.account_id == ws.account_id
    ).all()
    return [
        {"id": c.id, "name": c.name, "type": c.type, "is_system": c.is_system}
        for c in catalogs
    ]
