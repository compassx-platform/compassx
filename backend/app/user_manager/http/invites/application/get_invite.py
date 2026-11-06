def _bind():
    import app.user_manager.http.invites.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_invite(token: str, account_db: Session = Depends(get_account_db)):
    invite = _find_valid_invite(token, account_db)
    return InviteDetailsOut(
        id=invite.id,
        email=invite.email,
        target_scope=invite.target_scope,
        target_workspace_id=invite.target_workspace_id,
        proposed_account_role_id=invite.proposed_account_role_id,
        proposed_workspace_role_id=invite.proposed_workspace_role_id,
        status=invite.status,
        expires_at=invite.expires_at,
    )
