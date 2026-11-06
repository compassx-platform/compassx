def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_parent_groups(
    group_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    assert_group_exists(group_id, admin.account_id, account_db)

    nestings = account_db.query(UmGroupNesting).filter(
        UmGroupNesting.child_group_id == group_id
    ).all()
    parent_ids = [n.parent_group_id for n in nestings]
    if not parent_ids:
        return []

    parents = account_db.query(UmGroup).filter(
        UmGroup.id.in_(parent_ids),
        UmGroup.account_id == admin.account_id,
    ).all()
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            source=g.source,
            member_count=len(g.members),
            created_at=g.created_at,
        )
        for g in parents
    ]
