from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def remove_member(
    slug: str,
    member_id: str,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)

    m = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.id == member_id,
        WorkspaceMembership.workspace_id == ctx.workspace_id,
    ).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(m)
    db.commit()
