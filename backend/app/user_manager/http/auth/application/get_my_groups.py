def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_my_groups(
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
):
    from sqlalchemy import text

    # Recursively find all groups the user belongs to
    query = text("""
        WITH RECURSIVE my_groups AS (
            SELECT group_id FROM um_group_members WHERE user_id = :user_id
            UNION
            SELECT gn.parent_group_id
            FROM um_group_nestings gn
            JOIN my_groups mg ON gn.child_group_id = mg.group_id
        )
        SELECT g.id, g.name, g.source,
               (SELECT count(*) FROM um_group_members gm WHERE gm.group_id = g.id) as member_count
        FROM um_groups g
        JOIN my_groups mg ON g.id = mg.group_id
        WHERE g.account_id = :account_id
        ORDER BY g.name ASC;
    """)

    rows = account_db.execute(query, {
        "user_id": user.id,
        "account_id": user.account_id,
    }).fetchall()

    return [
        MyGroupOut(
            id=str(r[0]),
            name=str(r[1]),
            source=str(r[2]),
            member_count=int(r[3]),
        )
        for r in rows
    ]
