def _bind():
    import app.user_manager.http.setup.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def setup_status(account_db: Session = Depends(get_account_db)):
    """Check whether initial setup has been completed."""
    from app.workspace.models import Account
    account = account_db.query(Account).first()
    if account is None:
        return {"needs_setup": True}
    # Check setup_completed column if it exists
    setup_completed = getattr(account, "setup_completed", None)
    if setup_completed is None:
        # Column doesn't exist yet; check if any UmUser exists as proxy
        user_count = account_db.query(UmUser).count()
        return {"needs_setup": user_count == 0}
    return {"needs_setup": not setup_completed}
