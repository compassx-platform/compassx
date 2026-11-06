from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def publish_object(
    slug: str,
    object_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    obj = db.query(CatalogObject).filter(CatalogObject.id == object_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="Object not found")
    if obj.home_workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=403, detail="Object belongs to a different workspace")
    if obj.visibility == "global":
        raise HTTPException(status_code=400, detail="Object already published")

    # Check PUBLISH privilege
    perm = db.query(CatalogPermission).filter(
        CatalogPermission.securable_type == "object",
        CatalogPermission.securable_id == object_id,
        CatalogPermission.principal_id == ctx.principal_id,
        CatalogPermission.privilege == "PUBLISH",
    ).first()
    # Schema MANAGE also grants publish
    schema_manage = db.query(CatalogPermission).filter(
        CatalogPermission.securable_type == "schema",
        CatalogPermission.securable_id == obj.schema_id,
        CatalogPermission.principal_id == ctx.principal_id,
        CatalogPermission.privilege == "MANAGE",
    ).first()

    if perm is None and schema_manage is None and not ctx.is_account_admin:
        raise HTTPException(status_code=403, detail="PUBLISH privilege required")

    obj.visibility = "global"
    obj.home_workspace_id = None
    db.commit()
    return {"status": "published", "object_id": object_id}
