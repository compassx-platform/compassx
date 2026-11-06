def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def reactivate_user(
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    user = account_db.query(UmUser).filter(
        UmUser.id == user_id, UmUser.account_id == admin.account_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status == "deactivated":
        raise HTTPException(status_code=400, detail="Cannot reactivate a deactivated user")
    user.status = "active"
    log_action(account_db, admin.account_id, "user_reactivated", "user",
               actor_user_id=admin.id, target_id=user_id)
    account_db.commit()
    return {"status": "active", "user_id": user_id}
