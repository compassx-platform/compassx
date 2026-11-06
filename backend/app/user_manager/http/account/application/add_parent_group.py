def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def add_parent_group(
    group_id: str,
    body: GroupParentAdd,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.cross_db import assert_group_exists
    from sqlalchemy import text

    assert_group_exists(group_id, admin.account_id, account_db)
    assert_group_exists(body.parent_group_id, admin.account_id, account_db)

    if group_id == body.parent_group_id:
        raise HTTPException(status_code=400, detail="A group cannot be a parent of itself")

    # Cycle detection: check if group_id is already an ancestor of parent_group_id
    cycle_check_query = text("""
        WITH RECURSIVE ancestors AS (
            SELECT parent_group_id FROM um_group_nestings WHERE child_group_id = :parent_id
            UNION
            SELECT gn.parent_group_id
            FROM um_group_nestings gn
            JOIN ancestors a ON gn.child_group_id = a.parent_group_id
        )
        SELECT 1 FROM ancestors WHERE parent_group_id = :child_id LIMIT 1;
    """)
    has_cycle = account_db.execute(cycle_check_query, {
        "parent_id": body.parent_group_id,
        "child_id": group_id,
    }).first()
    if has_cycle:
        raise HTTPException(status_code=400, detail="Circular group nesting detected")

    existing = account_db.query(UmGroupNesting).filter(
        UmGroupNesting.parent_group_id == body.parent_group_id,
        UmGroupNesting.child_group_id == group_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Group is already nested under this parent")

    nesting = UmGroupNesting(
        parent_group_id=body.parent_group_id,
        child_group_id=group_id,
    )
    account_db.add(nesting)
    log_action(account_db, admin.account_id, "group_nested", "group",
               actor_user_id=admin.id, target_id=group_id,
               metadata={"parent_group_id": body.parent_group_id})
    account_db.commit()
    return {"child_group_id": group_id, "parent_group_id": body.parent_group_id}
