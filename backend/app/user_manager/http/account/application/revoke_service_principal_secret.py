def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def revoke_service_principal_secret(
    sp_id: str,
    secret_id: str,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")

    sec = account_db.query(UmServicePrincipalSecret).filter(
        UmServicePrincipalSecret.id == secret_id,
        UmServicePrincipalSecret.sp_id == sp_id,
    ).first()
    if not sec:
        raise HTTPException(status_code=404, detail="Secret not found")

    account_db.delete(sec)
    log_action(account_db, admin.account_id, "sp_secret_revoked", "service_principal",
               actor_user_id=admin.id, target_id=sp.id, metadata={"secret_id": secret_id})
    account_db.commit()
    return {"status": "revoked", "secret_id": secret_id}
