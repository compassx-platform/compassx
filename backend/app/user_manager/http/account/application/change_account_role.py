def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def change_account_role(
    target_user_id: str,
    body: RolePatch,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    from app.user_manager.models.account_models import UmAccountRole
    if not account_db.get(UmAccountRole, body.role_id):
        raise HTTPException(status_code=400, detail=f"Unknown account role: {body.role_id}")

    existing = account_db.query(UmAccountRoleAssignment).filter(
        UmAccountRoleAssignment.account_id == admin.account_id,
        UmAccountRoleAssignment.principal_id == target_user_id,
        UmAccountRoleAssignment.principal_type == "user",
    ).first()
    if existing:
        existing.role_id = body.role_id
        existing.granted_by = admin.id
    else:
        account_db.add(UmAccountRoleAssignment(
            account_id=admin.account_id,
            principal_id=target_user_id,
            principal_type="user",
            role_id=body.role_id,
            granted_by=admin.id,
        ))
    log_action(account_db, admin.account_id, "role_granted", "user",
               actor_user_id=admin.id, target_id=target_user_id,
               metadata={"role_id": body.role_id})
    invalidate_entry_point_cache(target_user_id)
    account_db.commit()
    return {"target_user_id": target_user_id, "role_id": body.role_id}
