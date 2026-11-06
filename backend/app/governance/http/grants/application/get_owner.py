from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_owner(
    securable_type: SecurableType,
    name: str,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> OwnerOut | None:
    """Who owns an object. Visible to anyone who can see the object.

    Deliberately readable at BROWSE: the owner is who you ask for access, so
    hiding it would leave a user who has been denied with nowhere to go.
    """
    securable = SecurableRef(securable_type=securable_type, name=name).to_securable()
    guard.require(Privilege.BROWSE, securable)
    row = service.get_owner(db, guard.workspace_id, securable)
    if row is None:
        return None
    return OwnerOut(
        securable_type=row.securable_type,
        securable_name=securable.full_name,
        owner_principal_id=row.owner_principal_id,
        owner_principal_type=row.owner_principal_type,
        assigned_at=row.assigned_at,
    )
