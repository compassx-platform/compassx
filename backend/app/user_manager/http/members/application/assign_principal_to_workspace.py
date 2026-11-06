def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def assign_principal_to_workspace(
    workspace_id: str,
    body: AssignPrincipalIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Assign an existing Account User, Group, or Service Principal to a workspace."""
    _require_ws_admin(workspace_id, user, account_db, system_db)
    assert_workspace_exists_in_account_db(workspace_id, account_db)
    _valid_ws_role(body.role_id, system_db)

    # Validate principal exists in account_db
    if body.principal_type == "user":
        target = account_db.query(UmUser).filter(
            UmUser.id == body.principal_id,
            UmUser.account_id == user.account_id,
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Account user not found")
    elif body.principal_type == "group":
        target = account_db.query(UmGroup).filter(
            UmGroup.id == body.principal_id,
            UmGroup.account_id == user.account_id,
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Account group not found")
    elif body.principal_type == "service_principal":
        target = account_db.query(UmServicePrincipal).filter(
            UmServicePrincipal.id == body.principal_id,
            UmServicePrincipal.account_id == user.account_id,
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Account service principal not found")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported principal type: {body.principal_type}")

    # Check existing assignment
    existing = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == body.principal_id,
    ).first()

    if existing:
        existing.role_id = body.role_id
        existing.principal_type = body.principal_type
        existing.granted_by = user.id
    else:
        system_db.add(UmWorkspaceRoleAssignment(
            workspace_id=workspace_id,
            principal_id=body.principal_id,
            principal_type=body.principal_type,
            role_id=body.role_id,
            granted_by=user.id,
        ))

    log_action(account_db, user.account_id, "workspace_principal_assigned", body.principal_type,
               actor_user_id=user.id, target_id=body.principal_id, workspace_id=workspace_id,
               metadata={"role_id": body.role_id, "principal_type": body.principal_type})
    system_db.commit()
    account_db.commit()
    invalidate_entry_point_cache(body.principal_id if body.principal_type == "user" else None)

    return {"status": "assigned", "principal_id": body.principal_id, "role_id": body.role_id}
