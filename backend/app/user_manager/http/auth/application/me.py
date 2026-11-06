def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def me(
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
):
    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        account_id=user.account_id,
        status=user.status,
        account_role=account_role,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )
