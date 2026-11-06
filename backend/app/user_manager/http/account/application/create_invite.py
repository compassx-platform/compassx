def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_invite(
    body: InviteIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    if body.target_scope not in ("account", "workspace"):
        raise HTTPException(status_code=400, detail="target_scope must be 'account' or 'workspace'")
    if body.target_scope == "workspace" and not body.target_workspace_id:
        raise HTTPException(status_code=400, detail="target_workspace_id required for workspace scope")

    email = body.email.lower().strip()
    # Check if user already exists
    existing_user = account_db.query(UmUser).filter(
        UmUser.email == email, UmUser.account_id == admin.account_id
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists in this account")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_refresh_token(raw_token)  # SHA-256 same as refresh tokens

    invite = UmInvite(
        account_id=admin.account_id,
        email=email,
        token_hash=token_hash,
        target_scope=body.target_scope,
        target_workspace_id=body.target_workspace_id,
        proposed_account_role_id=body.proposed_account_role_id,
        proposed_workspace_role_id=body.proposed_workspace_role_id,
        invited_by=admin.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    account_db.add(invite)
    log_action(account_db, admin.account_id, "invite_created", "invite",
               actor_user_id=admin.id,
               metadata={"email": email, "target_scope": body.target_scope})
    account_db.commit()
    account_db.refresh(invite)

    frontend_origin = __import__("os").environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
    invite_url = f"{frontend_origin}/invite/{raw_token}"
    logger.info("INVITE URL (stub email): %s", invite_url)  # stub — log instead of email

    return _invite_to_out(invite, frontend_origin, raw_token)
