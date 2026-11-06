def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_users(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    users = account_db.query(UmUser).filter(UmUser.account_id == admin.account_id).all()
    result = []
    for u in users:
        ws_count = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.principal_id == u.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        ).count()
        role = get_effective_account_role(u.id, u.account_id, account_db)
        result.append(UserListItem(
            id=u.id, email=u.email, display_name=u.display_name,
            status=u.status, account_role=role, workspace_count=ws_count,
            last_login_at=u.last_login_at, created_at=u.created_at,
        ))
    return result
