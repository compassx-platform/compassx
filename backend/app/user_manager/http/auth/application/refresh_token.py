def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def refresh_token(body: RefreshIn, account_db: Session = Depends(get_account_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    row = (
        account_db.query(UmRefreshToken)
        .filter(
            UmRefreshToken.token_hash == token_hash,
            UmRefreshToken.revoked_at == None,
            UmRefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = account_db.query(UmUser).filter(UmUser.id == row.user_id).first()
    if user is None or user.status in ("suspended", "deactivated"):
        row.revoked_at = datetime.now(timezone.utc)
        account_db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not active")

    account_roles = [
        r.role_id
        for r in account_db.query(UmAccountRoleAssignment)
        .filter(
            UmAccountRoleAssignment.principal_id == user.id,
            UmAccountRoleAssignment.principal_type == "user",
        )
        .all()
    ]
    access = create_access_token(user.id, user.account_id, account_roles)
    account_db.commit()
    return TokenOut(access_token=access)
