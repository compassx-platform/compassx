def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def login(body: LoginIn, account_db: Session = Depends(get_account_db)):
    user = (
        account_db.query(UmUser)
        .filter(UmUser.email == body.email.lower().strip())
        .first()
    )
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.status == "suspended":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended")
    if user.status == "deactivated":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    if user.status == "invited":
        # Allow login after invitation — they set their password during acceptance
        user.status = "active"

    user.last_login_at = datetime.now(timezone.utc)
    access, raw_refresh = _issue_tokens(user, account_db)
    account_db.commit()

    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    return LoginOut(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        account_id=user.account_id,
        is_account_admin=(account_role == "account_admin"),
    )
