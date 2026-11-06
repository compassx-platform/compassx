def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_group(
    body: GroupCreate,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    existing = account_db.query(UmGroup).filter(
        UmGroup.account_id == admin.account_id, UmGroup.name == body.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group name already exists")
    g = UmGroup(account_id=admin.account_id, name=body.name)
    account_db.add(g)
    account_db.commit()
    account_db.refresh(g)
    return GroupOut(id=g.id, name=g.name, source=g.source, member_count=0, created_at=g.created_at)
