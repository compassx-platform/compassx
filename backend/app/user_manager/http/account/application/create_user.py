def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_user(
    body: UserCreateIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
    system_db: Session = Depends(get_system_db),
):
    """Directly provision a new user in the account (account_admin only)."""
    email = body.email.lower().strip()
    existing = account_db.query(UmUser).filter(
        UmUser.email == email, UmUser.account_id == admin.account_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = UmUser(
        account_id=admin.account_id,
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
        auth_provider="local",
        status="active",
    )
    account_db.add(user)
    account_db.flush()

    # Assign requested account role
    from app.user_manager.models.account_models import UmAccountRole
    role_id = body.account_role if account_db.get(UmAccountRole, body.account_role) else "account_viewer"
    account_db.add(UmAccountRoleAssignment(
        account_id=admin.account_id,
        principal_id=user.id,
        principal_type="user",
        role_id=role_id,
        granted_by=admin.id,
    ))

    log_action(
        account_db, admin.account_id, "user_created", "user",
        actor_user_id=admin.id, target_id=user.id,
        metadata={"email": email, "account_role": role_id},
    )
    account_db.commit()
    account_db.refresh(user)

    return UserListItem(
        id=user.id, email=user.email, display_name=user.display_name,
        status=user.status, account_role=role_id, workspace_count=0,
        last_login_at=user.last_login_at, created_at=user.created_at,
    )
