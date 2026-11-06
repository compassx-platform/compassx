def _bind():
    import app.user_manager.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def authenticate_service_principal(
    body: ServicePrincipalTokenIn,
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.models.account_models import UmServicePrincipal, UmServicePrincipalSecret

    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.application_id == body.application_id,
        UmServicePrincipal.is_active == True,
    ).first()
    if not sp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid application ID or secret")

    now = datetime.now(timezone.utc)
    secrets = account_db.query(UmServicePrincipalSecret).filter(
        UmServicePrincipalSecret.sp_id == sp.id,
    ).all()

    valid_secret = None
    for s in secrets:
        if s.expires_at and s.expires_at < now:
            continue
        if verify_password(body.client_secret, s.secret_hash):
            valid_secret = s
            break

    if not valid_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid application ID or secret")

    access = create_access_token(
        user_id=sp.id,
        account_id=sp.account_id,
        account_roles=["service_principal"],
    )

    return ServicePrincipalTokenOut(
        access_token=access,
        token_type="bearer",
        sp_id=sp.id,
        application_id=sp.application_id,
        display_name=sp.display_name,
        account_id=sp.account_id,
    )
