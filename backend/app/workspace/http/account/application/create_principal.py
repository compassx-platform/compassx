from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_principal(
    body: PrincipalCreate,
    db: Session = Depends(get_account_db),
    admin: Principal = Depends(require_account_admin),
):
    if body.type not in ("user", "group", "service_principal"):
        raise HTTPException(status_code=400, detail="Invalid principal type")
    if body.email:
        existing = db.query(Principal).filter(
            Principal.account_id == admin.account_id,
            Principal.email == body.email,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists in this account")

    pw_hash = hash_password(body.password) if body.password else None
    p = Principal(
        id=str(uuid4()),
        account_id=admin.account_id,
        type=body.type,
        email=body.email,
        name=body.name,
        password_hash=pw_hash,
        is_account_admin=body.is_account_admin,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p
