from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def list_principal_grants(
    principal_id: str,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> list[GrantOut]:
    """Everything one principal holds — the access review for a user or agent.

    Workspace-admin only. A principal may inspect their own access.
    """
    if principal_id != guard.principal.id:
        _require_workspace_admin(guard)
    rows = service.list_principal_grants(db, guard.workspace_id, principal_id)
    return [_to_grant_out(row) for row in rows]
