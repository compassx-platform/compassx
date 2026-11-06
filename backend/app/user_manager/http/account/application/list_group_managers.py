def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_group_managers(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    g = assert_group_exists(group_id, admin.account_id, account_db)
    result = []
    for m in g.managers:
        u = account_db.query(UmUser).filter(UmUser.id == m.user_id).first()
        if u:
            result.append(GroupManagerOut(
                user_id=u.id,
                email=u.email,
                display_name=u.display_name,
                assigned_at=m.assigned_at,
            ))
    return result
