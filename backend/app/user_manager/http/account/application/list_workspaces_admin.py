def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_workspaces_admin(
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    from app.workspace.models import Workspace as LegacyWs
    workspaces = account_db.query(LegacyWs).filter(LegacyWs.account_id == admin.account_id).all()
    result = []
    for ws in workspaces:
        member_count = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.workspace_id == ws.id
        ).count()
        result.append(WorkspaceAdminOut(
            id=ws.id, name=ws.name, slug=ws.slug,
            status=ws.status, member_count=member_count,
            created_at=ws.created_at,
        ))
    return result
