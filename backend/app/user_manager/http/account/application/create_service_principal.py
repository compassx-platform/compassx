def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_service_principal(
    body: ServicePrincipalCreate,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    name = body.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="display_name cannot be empty")
    sp = UmServicePrincipal(
        account_id=admin.account_id,
        display_name=name,
    )
    account_db.add(sp)
    log_action(account_db, admin.account_id, "service_principal_created", "service_principal",
               actor_user_id=admin.id, metadata={"display_name": name, "application_id": sp.application_id})
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
        secret_count=0,
    )
