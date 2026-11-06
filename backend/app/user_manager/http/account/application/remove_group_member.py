def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def remove_group_member(
    group_id: str,
    user_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)
    gm = account_db.query(UmGroupMember).filter(
        UmGroupMember.group_id == group_id, UmGroupMember.user_id == user_id
    ).first()
    if not gm:
        raise HTTPException(status_code=404, detail="Member not found")
    account_db.delete(gm)
    invalidate_entry_point_cache(user_id)
    account_db.commit()
    return {"group_id": group_id, "user_id": user_id, "status": "removed"}
