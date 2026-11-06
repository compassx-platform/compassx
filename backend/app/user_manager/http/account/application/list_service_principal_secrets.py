def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_service_principal_secrets(
    sp_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")
    secrets_list = account_db.query(UmServicePrincipalSecret).filter(
        UmServicePrincipalSecret.sp_id == sp_id
    ).all()
    return [
        SecretMetadataOut(
            id=s.id,
            sp_id=s.sp_id,
            secret_prefix=s.secret_prefix,
            expires_at=s.expires_at,
            created_at=s.created_at,
        )
        for s in secrets_list
    ]
