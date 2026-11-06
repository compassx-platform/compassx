from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_principal(
    principal_id: str,
    body: PrincipalPatch,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    p = db.query(Principal).filter(
        Principal.id == principal_id,
        Principal.account_id == admin.account_id,
    ).first()
    if p is None:
        raise HTTPException(status_code=404, detail="Principal not found")
    if body.name is not None:
        p.name = body.name
    if body.is_account_admin is not None:
        p.is_account_admin = body.is_account_admin
    if body.is_active is not None:
        p.is_active = body.is_active
    db.commit()
    db.refresh(p)
    return p
