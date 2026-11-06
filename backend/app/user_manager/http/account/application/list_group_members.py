def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_group_members(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    g = assert_group_exists(group_id, admin.account_id, account_db)
    result = []
    for gm in g.members:
        u = account_db.query(UmUser).filter(UmUser.id == gm.user_id).first()
        if u:
            result.append(GroupMemberOut(
                user_id=u.id, email=u.email, display_name=u.display_name, added_at=gm.added_at
            ))
    return result
