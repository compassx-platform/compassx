def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def my_workspaces(
    user: UmUser = Depends(get_current_um_user),
    system_db: Session = Depends(get_system_db),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.models.account_models import UmGroupMember
    from app.workspace.models import Workspace as LegacyWs

    account_role = get_effective_account_role(user.id, user.account_id, account_db)
    is_admin = (account_role == "account_admin")

    # Direct assignments
    direct = (
        system_db.query(UmWorkspaceRoleAssignment)
        .filter(
            UmWorkspaceRoleAssignment.principal_id == user.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        )
        .all()
    )
    group_ids = [gm.group_id for gm in account_db.query(UmGroupMember).filter(UmGroupMember.user_id == user.id).all()]
    group_rows = []
    if group_ids:
        group_rows = (
            system_db.query(UmWorkspaceRoleAssignment)
            .filter(
                UmWorkspaceRoleAssignment.principal_id.in_(group_ids),
                UmWorkspaceRoleAssignment.principal_type == "group",
            )
            .all()
        )

    result = []
    seen = set()
    for row in direct + group_rows:
        if row.workspace_id in seen:
            continue
        seen.add(row.workspace_id)
        is_uuid = False
        try:
            from uuid import UUID
            UUID(str(row.workspace_id))
            is_uuid = True
        except (ValueError, TypeError):
            pass

        ws = account_db.query(LegacyWs).filter(
            LegacyWs.id == row.workspace_id if is_uuid else LegacyWs.slug == row.workspace_id
        ).first()
        if ws:
            seen.add(ws.id)
            seen.add(ws.slug)
        result.append(WorkspaceMembershipOut(
            workspace_id=ws.id if ws else row.workspace_id,
            workspace_name=ws.name if ws else None,
            workspace_slug=ws.slug if ws else None,
            role_id=row.role_id,
            is_default=row.is_default,
        ))

    # If user is account_admin, ensure ALL active workspaces in user's account (or system) are included
    if is_admin:
        all_account_workspaces = (
            account_db.query(LegacyWs)
            .filter(
                (LegacyWs.account_id == user.account_id) | (LegacyWs.account_id.is_(None)),
                LegacyWs.status == "active"
            )
            .all()
        )
        if not all_account_workspaces:
            all_account_workspaces = (
                account_db.query(LegacyWs)
                .filter(LegacyWs.status == "active")
                .all()
            )
        for ws in all_account_workspaces:
            if ws.id not in seen and ws.slug not in seen:
                seen.add(ws.id)
                seen.add(ws.slug)
                result.append(WorkspaceMembershipOut(
                    workspace_id=ws.id,
                    workspace_name=ws.name,
                    workspace_slug=ws.slug,
                    role_id="workspace_admin",
                    is_default=(len(result) == 0),
                ))

    return result
