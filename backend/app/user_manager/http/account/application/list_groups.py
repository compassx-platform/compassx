def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_groups(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    groups = account_db.query(UmGroup).filter(UmGroup.account_id == admin.account_id).all()
    return [GroupOut(
        id=g.id, name=g.name, source=g.source,
        member_count=len(g.members), created_at=g.created_at,
    ) for g in groups]
