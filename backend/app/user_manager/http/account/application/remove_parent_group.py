def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def remove_parent_group(
    group_id: str,
    parent_group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    nesting = account_db.query(UmGroupNesting).filter(
        UmGroupNesting.parent_group_id == parent_group_id,
        UmGroupNesting.child_group_id == group_id,
    ).first()
    if not nesting:
        raise HTTPException(status_code=404, detail="Parent group relationship not found")

    account_db.delete(nesting)
    log_action(account_db, admin.account_id, "group_unnested", "group",
               actor_user_id=admin.id, target_id=group_id,
               metadata={"parent_group_id": parent_group_id})
    account_db.commit()
    return {"child_group_id": group_id, "parent_group_id": parent_group_id, "status": "removed"}
