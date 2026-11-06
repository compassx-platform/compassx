from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_objects(
    slug: str,
    catalog_name: str,
    schema_name: str,
    request: Request,
    object_type: str | None = None,
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

    from app.workspace.models import WorkspaceCatalogSchema
    schema = db.query(WorkspaceCatalogSchema).filter(
        WorkspaceCatalogSchema.catalog_id == catalog.id,
        WorkspaceCatalogSchema.name == schema_name,
    ).first()
    if schema is None:
        raise HTTPException(status_code=404, detail="Schema not found")

    q = db.query(CatalogObject).filter(
        CatalogObject.schema_id == schema.id,
        (CatalogObject.visibility == "global") |
        (CatalogObject.home_workspace_id == ctx.workspace_id),
    )
    if object_type:
        q = q.filter(CatalogObject.object_type == object_type)
    return q.all()
