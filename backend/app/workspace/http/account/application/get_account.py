from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_account(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    account = db.query(Account).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account
