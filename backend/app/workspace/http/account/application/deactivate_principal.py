from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def deactivate_principal(
    principal_id: str,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    p = db.query(Principal).filter(
        Principal.id == principal_id,
        Principal.account_id == admin.account_id,
    ).first()
    if p is None:
        raise HTTPException(status_code=404, detail="Principal not found")
    p.is_active = False
    db.commit()
