def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_service_principal(
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
    return ServicePrincipalOut(
        id=sp.id,
        account_id=sp.account_id,
        application_id=sp.application_id,
        display_name=sp.display_name,
        source=sp.source,
        is_active=sp.is_active,
        created_at=sp.created_at,
        secret_count=len(sp.secrets),
    )
