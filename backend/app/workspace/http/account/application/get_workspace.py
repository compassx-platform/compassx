from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.account_id == _admin.account_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, status=ws.status,
        storage_backend=ws.storage_backend,
        url=f"/w/{ws.slug}",
        created_at=ws.created_at,
    )
