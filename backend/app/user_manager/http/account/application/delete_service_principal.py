def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def delete_service_principal(
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
    account_db.delete(sp)
    log_action(account_db, admin.account_id, "service_principal_deleted", "service_principal",
               actor_user_id=admin.id, target_id=sp_id)
    account_db.commit()
    return {"status": "deleted", "sp_id": sp_id}
