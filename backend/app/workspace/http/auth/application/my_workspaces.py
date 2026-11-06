from __future__ import annotations

def _bind():
    import app.workspace.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def my_workspaces(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_account_db),
):
    if principal.is_account_admin:
        workspaces = db.query(Workspace).filter(Workspace.status == "active").all()
        return [
            WorkspaceSlim(
                id=w.id, name=w.name, slug=w.slug, status=w.status,
                url=f"/w/{w.slug}", role="admin"
            )
            for w in workspaces
        ]

    memberships = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.principal_id == principal.id)
        .all()
    )
    result = []
    for m in memberships:
        w = db.query(Workspace).filter(Workspace.id == m.workspace_id, Workspace.status == "active").first()
        if w:
            result.append(WorkspaceSlim(
                id=w.id, name=w.name, slug=w.slug, status=w.status,
                url=f"/w/{w.slug}", role=m.role,
            ))
    return result
