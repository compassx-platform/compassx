from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_workspaces(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    return [
        WorkspaceOut(
            id=w.id, name=w.name, slug=w.slug, status=w.status,
            storage_backend=w.storage_backend,
            url=f"/w/{w.slug}",
            created_at=w.created_at,
        )
        for w in db.query(Workspace).filter(Workspace.account_id == _admin.account_id).all()
    ]
