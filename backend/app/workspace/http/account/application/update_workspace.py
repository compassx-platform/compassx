from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_workspace(
    workspace_id: str,
    body: WorkspacePatch,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.account_id == _admin.account_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if body.name is not None:
        ws.name = body.name
    if body.storage_config is not None:
        ws.storage_config = encrypt_storage_config(body.storage_config)
    db.commit()
    db.refresh(ws)
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, status=ws.status,
        storage_backend=ws.storage_backend,
        url=f"/w/{ws.slug}",
        created_at=ws.created_at,
    )
