def _bind():
    import app.user_manager.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def generate_service_principal_secret(
    sp_id: str,
    body: SecretGenerateIn,
    admin: UmUser = Depends(require_um_account_admin),
    account_db: Session = Depends(get_account_db),
):
    sp = account_db.query(UmServicePrincipal).filter(
        UmServicePrincipal.id == sp_id,
        UmServicePrincipal.account_id == admin.account_id,
    ).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Service Principal not found")

    raw_token = f"cpx_sp_{secrets.token_urlsafe(32)}"
    prefix = f"{raw_token[:12]}..."
    secret_hash = hash_password(raw_token)
    expires_at = None
    if body.expires_in_days and body.expires_in_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    sec = UmServicePrincipalSecret(
        sp_id=sp.id,
        secret_hash=secret_hash,
        secret_prefix=prefix,
        expires_at=expires_at,
    )
    account_db.add(sec)
    log_action(account_db, admin.account_id, "sp_secret_generated", "service_principal",
               actor_user_id=admin.id, target_id=sp.id, metadata={"secret_prefix": prefix})
    account_db.commit()
    account_db.refresh(sec)

    return SecretGenerateOut(
        id=sec.id,
        sp_id=sec.sp_id,
        secret_prefix=sec.secret_prefix,
        client_secret=raw_token,
        expires_at=sec.expires_at,
        created_at=sec.created_at,
    )
