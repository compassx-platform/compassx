from __future__ import annotations

def _bind():
    import app.workspace.http.workspace.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def add_member(
    slug: str,
    body: MemberAdd,
    request: Request,
    db: Session = Depends(get_account_db),
):
    ctx = _get_workspace_ctx(request)
    _require_workspace_admin(ctx)

    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = db.query(WorkspaceMembership).filter(
        WorkspaceMembership.workspace_id == ctx.workspace_id,
        WorkspaceMembership.principal_id == body.principal_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Principal already a member")

    principal = db.query(Principal).filter(Principal.id == body.principal_id).first()
    if principal is None:
        raise HTTPException(status_code=404, detail="Principal not found")

    m = WorkspaceMembership(
        id=str(uuid4()),
        workspace_id=ctx.workspace_id,
        principal_id=body.principal_id,
        role=body.role,
        granted_by=ctx.principal_id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return MemberOut(
        id=m.id,
        workspace_id=m.workspace_id,
        principal_id=m.principal_id,
        role=m.role,
        granted_at=m.granted_at,
        principal=principal,
    )
