def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def set_default_workspace(
    workspace_id: str,
    user: UmUser = Depends(get_current_um_user),
    system_db: Session = Depends(get_system_db),
    account_db: Session = Depends(get_account_db),
):
    """Set is_default=true for this workspace for the current user (§5.6)."""
    from app.workspace.models import Workspace as LegacyWs
    from app.user_manager.entry_point import _get_user_workspace_ids
    from uuid import UUID

    is_uuid = False
    try:
        UUID(str(workspace_id))
        is_uuid = True
    except (ValueError, TypeError):
        pass

    ws = account_db.query(LegacyWs).filter(
        (LegacyWs.id == workspace_id) if is_uuid else (LegacyWs.slug == workspace_id)
    ).first()
    if not ws:
        ws = account_db.query(LegacyWs).filter(
            (LegacyWs.id == workspace_id) | (LegacyWs.slug == workspace_id)
        ).first()

    canonical_ws_id = ws.id if ws else workspace_id

    # Verify user has access to this workspace (direct, group, or account admin)
    memberships = _get_user_workspace_ids(user.id, system_db, account_db)
    matching_role = next(
        (r for wid, r in memberships if wid == canonical_ws_id or wid == workspace_id or (ws and wid == ws.slug)),
        None,
    )
    if not matching_role:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    # Clear existing defaults for this user
    system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.principal_id == user.id,
        UmWorkspaceRoleAssignment.principal_type == "user",
        UmWorkspaceRoleAssignment.is_default == True,
    ).update({"is_default": False})

    target = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == canonical_ws_id,
        UmWorkspaceRoleAssignment.principal_id == user.id,
        UmWorkspaceRoleAssignment.principal_type == "user",
    ).first()
    if not target:
        target = UmWorkspaceRoleAssignment(
            workspace_id=canonical_ws_id,
            principal_id=user.id,
            principal_type="user",
            role_id=matching_role or "workspace_admin",
            is_default=True,
        )
        system_db.add(target)
    else:
        target.is_default = True
    system_db.commit()
    invalidate_entry_point_cache(user.id)
    return {"workspace_id": canonical_ws_id, "is_default": True}
