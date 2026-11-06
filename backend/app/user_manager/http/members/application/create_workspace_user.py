def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_workspace_user(
    workspace_id: str,
    body: WorkspaceUserCreateIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Directly provision a new user and add them to the workspace in one step."""
    _require_ws_admin(workspace_id, user, account_db, system_db)
    assert_workspace_exists_in_account_db(workspace_id, account_db)
    _valid_ws_role(body.role_id, system_db)

    email = body.email.lower().strip()
    existing_user = account_db.query(UmUser).filter(
        UmUser.email == email, UmUser.account_id == user.account_id
    ).first()

    if existing_user:
        # User already exists in account_db — grant or update workspace access directly
        ass = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.workspace_id == workspace_id,
            UmWorkspaceRoleAssignment.principal_id == existing_user.id,
        ).first()
        if ass:
            ass.role_id = body.role_id
            ass.principal_type = "user"
            ass.granted_by = user.id
        else:
            system_db.add(UmWorkspaceRoleAssignment(
                workspace_id=workspace_id,
                principal_id=existing_user.id,
                principal_type="user",
                role_id=body.role_id,
                granted_by=user.id,
            ))
        system_db.commit()
        account_db.commit()
        invalidate_entry_point_cache(existing_user.id)
        return {"id": existing_user.id, "email": existing_user.email, "display_name": existing_user.display_name, "status": "added_existing"}

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    from app.user_manager.auth_utils import hash_password

    new_user = UmUser(
        account_id=user.account_id,
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        auth_provider="local",
        status="active",
    )
    account_db.add(new_user)
    account_db.flush()

    # Assign default account_viewer role in account_db
    account_db.add(UmAccountRoleAssignment(
        account_id=user.account_id,
        principal_id=new_user.id,
        principal_type="user",
        role_id="account_viewer",
        granted_by=user.id,
    ))

    # Assign requested workspace role in system_db
    system_db.add(UmWorkspaceRoleAssignment(
        workspace_id=workspace_id,
        principal_id=new_user.id,
        principal_type="user",
        role_id=body.role_id,
        granted_by=user.id,
    ))

    log_action(account_db, user.account_id, "user_created", "user",
               actor_user_id=user.id, target_id=new_user.id, workspace_id=workspace_id,
               metadata={"email": email, "workspace_role": body.role_id})

    account_db.commit()
    system_db.commit()

    return {"type": "created", "user_id": new_user.id, "email": new_user.email, "role_id": body.role_id}
