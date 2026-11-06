def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def revoke_invite(
    invite_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    invite = account_db.query(UmInvite).filter(
        UmInvite.id == invite_id, UmInvite.account_id == admin.account_id
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.status = "revoked"
    log_action(account_db, admin.account_id, "invite_revoked", "invite",
               actor_user_id=admin.id, target_id=invite_id)
    account_db.commit()
    return {"status": "revoked", "invite_id": invite_id}
