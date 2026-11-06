from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_schemas(
    slug: str,
    catalog_name: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    ws = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    catalog = db.query(WorkspaceCatalog).filter(
        WorkspaceCatalog.account_id == ws.account_id,
        WorkspaceCatalog.name == catalog_name,
    ).first()
    if catalog is None:
        raise HTTPException(status_code=404, detail="Catalog not found")
    return [{"id": s.id, "name": s.name} for s in catalog.schemas]
