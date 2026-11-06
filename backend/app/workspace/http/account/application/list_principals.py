from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_principals(
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    return db.query(Principal).filter(Principal.account_id == admin.account_id).all()
