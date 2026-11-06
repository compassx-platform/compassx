from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_grants(
    securable_type: SecurableType,
    name: str,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> list[GrantOut]:
    """Grants made directly on one object — the Permissions tab.

    Requires MANAGE: who holds access to an object is itself sensitive.
    """
    securable = SecurableRef(securable_type=securable_type, name=name).to_securable()
    guard.require(Privilege.MANAGE, securable)
    rows = service.list_grants(db, guard.workspace_id, securable)
    return [_to_grant_out(row) for row in rows]
