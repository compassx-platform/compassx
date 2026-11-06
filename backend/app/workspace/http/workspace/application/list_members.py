from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_members(
    slug: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    memberships = (
        db.query(WorkspaceMembership)
        .filter(WorkspaceMembership.workspace_id == ctx.workspace_id)
        .all()
    )
    result = []
    for m in memberships:
        principal = db.query(Principal).filter(Principal.id == m.principal_id).first()
        result.append(MemberOut(
            id=m.id,
            workspace_id=m.workspace_id,
            principal_id=m.principal_id,
            role=m.role,
            granted_at=m.granted_at,
            principal=principal,
        ))
    return result
