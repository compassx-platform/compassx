def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def logout(body: RefreshIn, account_db: Session = Depends(get_account_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    row = account_db.query(UmRefreshToken).filter(UmRefreshToken.token_hash == token_hash).first()
    if row:
        row.revoked_at = datetime.now(timezone.utc)
        account_db.commit()
