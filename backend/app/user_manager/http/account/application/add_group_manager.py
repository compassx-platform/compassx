def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def add_group_manager(
    group_id: str,
    body: GroupManagerAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    user = account_db.query(UmUser).filter(
        UmUser.id == body.user_id,
        UmUser.account_id == admin.account_id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = account_db.query(UmGroupManager).filter(
        UmGroupManager.group_id == group_id,
        UmGroupManager.user_id == body.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a manager of this group")

    mgr = UmGroupManager(group_id=group_id, user_id=body.user_id)
    account_db.add(mgr)
    log_action(account_db, admin.account_id, "group_manager_added", "group",
               actor_user_id=admin.id, target_id=group_id, metadata={"user_id": body.user_id})
    account_db.commit()
    return {"group_id": group_id, "user_id": body.user_id}
