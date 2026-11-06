def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_member_role(
    workspace_id: str,
    principal_id: str,
    body: RolePatch,
    actor: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    _require_ws_admin(workspace_id, actor, account_db, system_db)
    _valid_ws_role(body.role_id, system_db)

    row = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == principal_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Membership not found")
    row.role_id = body.role_id
    row.granted_by = actor.id
    log_action(account_db, actor.account_id, "role_changed", str(row.principal_type),
               actor_user_id=actor.id, target_id=principal_id, workspace_id=workspace_id,
               metadata={"role_id": body.role_id})
    system_db.commit()
    account_db.commit()
    invalidate_entry_point_cache(principal_id)
    return {"principal_id": principal_id, "workspace_id": workspace_id, "role_id": body.role_id}
