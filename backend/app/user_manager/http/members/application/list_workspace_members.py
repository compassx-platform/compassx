def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_workspace_members(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    # Any workspace member (or account admin) can view the list
    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    ws_role = get_effective_workspace_role(user.id, workspace_id, system_db, account_db)
    if account_role != "account_admin" and ws_role is None:
        raise HTTPException(status_code=403, detail="No access to this workspace")

    rows = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id
    ).all()

    result = []
    for row in rows:
        email = None
        display = None
        client_id = None
        member_count = None
        pt = str(row.principal_type.value if hasattr(row.principal_type, "value") else row.principal_type)

        if pt == "user":
            u = account_db.query(UmUser).filter(UmUser.id == row.principal_id).first()
            if u:
                email = u.email
                display = u.display_name or u.email
        elif pt == "group":
            g = account_db.query(UmGroup).filter(UmGroup.id == row.principal_id).first()
            if g:
                display = g.name
                member_count = len(g.members)
        elif pt == "service_principal":
            sp = account_db.query(UmServicePrincipal).filter(UmServicePrincipal.id == row.principal_id).first()
            if sp:
                display = sp.display_name
                client_id = sp.client_id

        result.append(MemberOut(
            assignment_id=row.id,
            principal_id=row.principal_id,
            user_id=row.principal_id if pt == "user" else None,
            group_id=row.principal_id if pt == "group" else None,
            sp_id=row.principal_id if pt == "service_principal" else None,
            principal_type=pt,
            email=email,
            display_name=display,
            client_id=client_id,
            member_count=member_count,
            role_id=row.role_id,
            is_default=row.is_default,
            granted_at=row.granted_at,
        ))
    return result
