def _bind():
    import app.user_manager.http.invites.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def accept_invite(
    token: str,
    body: AcceptIn,
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    invite = _find_valid_invite(token, account_db)

    # Create or activate user
    user = account_db.query(UmUser).filter(
        UmUser.email == invite.email,
        UmUser.account_id == invite.account_id,
    ).first()
    if user is None:
        user = UmUser(
            account_id=invite.account_id,
            email=invite.email,
            display_name=body.display_name,
            password_hash=hash_password(body.password),
            auth_provider="local",
            status="active",
        )
        account_db.add(user)
        account_db.flush()
    else:
        user.display_name = body.display_name
        user.password_hash = hash_password(body.password)
        user.status = "active"

    # Assign proposed account role if any
    if invite.proposed_account_role_id:
        existing_ara = account_db.query(UmAccountRoleAssignment).filter(
            UmAccountRoleAssignment.account_id == invite.account_id,
            UmAccountRoleAssignment.principal_id == user.id,
            UmAccountRoleAssignment.principal_type == "user",
        ).first()
        if not existing_ara:
            account_db.add(UmAccountRoleAssignment(
                account_id=invite.account_id,
                principal_id=user.id,
                principal_type="user",
                role_id=invite.proposed_account_role_id,
                granted_by=invite.invited_by,
            ))

    # Assign workspace membership if workspace-scoped
    if invite.target_scope == "workspace" and invite.target_workspace_id and invite.proposed_workspace_role_id:
        existing_wra = system_db.query(UmWorkspaceRoleAssignment).filter(
            UmWorkspaceRoleAssignment.workspace_id == invite.target_workspace_id,
            UmWorkspaceRoleAssignment.principal_id == user.id,
            UmWorkspaceRoleAssignment.principal_type == "user",
        ).first()
        if not existing_wra:
            system_db.add(UmWorkspaceRoleAssignment(
                workspace_id=invite.target_workspace_id,
                principal_id=user.id,
                principal_type="user",
                role_id=invite.proposed_workspace_role_id,
                granted_by=invite.invited_by,
            ))

    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)

    log_action(account_db, invite.account_id, "invite_accepted", "user",
               target_id=user.id, metadata={"invite_id": invite.id})

    # Issue tokens
    account_roles = [invite.proposed_account_role_id] if invite.proposed_account_role_id else []
    access = create_access_token(user.id, invite.account_id, account_roles)
    raw_refresh = generate_refresh_token()
    account_db.add(UmRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
    ))

    account_db.commit()
    system_db.commit()

    return AcceptOut(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        account_id=invite.account_id,
    )
