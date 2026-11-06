def _bind():
    import app.user_manager.http.members.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def invite_or_add_member(
    workspace_id: str,
    body: InviteOrAddIn,
    user: UmUser = Depends(get_current_um_user),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """grant_workspace_access per §5.3.
    
    If email_or_user_id matches an existing user → add directly.
    If no user found → create a workspace-scoped invite.
    """
    _require_ws_admin(workspace_id, user, account_db, system_db)
    assert_workspace_exists_in_account_db(workspace_id, account_db)
    _valid_ws_role(body.role_id, system_db)

    email_or_id = body.email_or_user_id.strip()
    is_uuid = False
    try:
        from uuid import UUID
        UUID(email_or_id)
        is_uuid = True
    except (ValueError, TypeError):
        pass

    target_user = None
    if is_uuid:
        target_user = account_db.query(UmUser).filter(UmUser.id == email_or_id).first()

    if target_user is None:
        target_user = account_db.query(UmUser).filter(
            UmUser.email == email_or_id.lower(),
            UmUser.account_id == user.account_id,
        ).first()

    if target_user is None:
        # Create invite
        raw_token = secrets.token_urlsafe(32)
        invite = UmInvite(
            account_id=user.account_id,
            email=email_or_id.lower(),
            token_hash=hash_refresh_token(raw_token),
            target_scope="workspace",
            target_workspace_id=workspace_id,
            proposed_workspace_role_id=body.role_id,
            invited_by=user.id,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        account_db.add(invite)
        log_action(account_db, user.account_id, "invite_created", "invite",
                   actor_user_id=user.id, workspace_id=workspace_id,
                   metadata={"email": email_or_id, "role_id": body.role_id})
        account_db.commit()
        frontend_origin = __import__("os").environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
        invite_url = f"{frontend_origin}/invite/{raw_token}"
        logger.info("WORKSPACE INVITE URL (stub): %s", invite_url)
        return {"type": "invited", "invite_id": invite.id, "invite_url": invite_url}

    # Add directly via workspace_role_assignments
    existing = system_db.query(UmWorkspaceRoleAssignment).filter(
        UmWorkspaceRoleAssignment.workspace_id == workspace_id,
        UmWorkspaceRoleAssignment.principal_id == target_user.id,
    ).first()
    if existing:
        existing.role_id = body.role_id
        existing.principal_type = "user"
        existing.granted_by = user.id
    else:
        system_db.add(UmWorkspaceRoleAssignment(
            workspace_id=workspace_id,
            principal_id=target_user.id,
            principal_type="user",
            role_id=body.role_id,
            granted_by=user.id,
        ))
    log_action(account_db, user.account_id, "member_added", "user",
               actor_user_id=user.id, target_id=target_user.id, workspace_id=workspace_id,
               metadata={"role_id": body.role_id})
    system_db.commit()
    account_db.commit()
    invalidate_entry_point_cache(target_user.id)
    return {"type": "added", "user_id": target_user.id}
