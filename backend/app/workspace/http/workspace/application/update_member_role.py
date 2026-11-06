from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_member_role(
    slug: str,
    member_id: str,
    body: MemberPatch,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)

    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    m = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.id == member_id,
        WorkspaceMembership.workspace_id == ctx.workspace_id,
    ).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    m.role = body.role
    db.commit()
    db.refresh(m)
    principal = db.query(Principal).filter(Principal.id == m.principal_id).first()
    return MemberOut(
        id=m.id,
        workspace_id=m.workspace_id,
        principal_id=m.principal_id,
        role=m.role,
        granted_at=m.granted_at,
        principal=principal,
    )
