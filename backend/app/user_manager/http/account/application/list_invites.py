def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_invites(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    rows = account_db.query(UmInvite).filter(
        UmInvite.account_id == admin.account_id,
        UmInvite.status == "pending",
    ).all()
    base = str(__import__("os").environ.get("FRONTEND_ORIGIN", "http://localhost:5173"))
    return [_invite_to_out(r, base) for r in rows]
