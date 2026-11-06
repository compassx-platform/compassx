def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def update_service_principal(
    sp_id: str,
    body: ServicePrincipalPatch,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")
    if body.display_name is not None:
        sp.display_name = body.display_name.strip()
    if body.is_active is not None:
        sp.is_active = body.is_active
    log_action(account_db, admin.account_id, "service_principal_updated", "service_principal",
               actor_user_id=admin.id, target_id=sp.id,
               metadata={"display_name": sp.display_name, "is_active": sp.is_active})
    account_db.commit()
    account_db.refresh(sp)
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
