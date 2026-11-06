from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def effective_permissions(
    securable_type: SecurableType,
    name: str,
    principal_id: str | None = Query(
        default=None,
        description="Defaults to the caller. Inspecting another principal requires workspace admin.",
    ),
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> EffectiveOut:
    """What a principal can actually do here, and why.

    Answers the question an administrator has when access is not behaving as
    expected, without requiring them to reconstruct the resolution order.
    """
    securable = SecurableRef(securable_type=securable_type, name=name).to_securable()

    if principal_id is None or principal_id == guard.principal.id:
        permissions = guard.permissions
        subject = guard.principal
    else:
        _require_workspace_admin(guard)
        subject = Principal(
            id=principal_id,
            workspace_roles={guard.workspace_id: "analyst"},
        )
        permissions = load_permission_set(db, subject, guard.workspace_id)

    applicable = sorted(
        APPLICABLE_PRIVILEGES.get(securable.type, frozenset()),
        key=lambda p: p.value,
    )
    decisions = {p.value: permissions.check(p, securable) for p in applicable}

    owner = service.get_owner(db, guard.workspace_id, securable)
    return EffectiveOut(
        principal_id=subject.id,
        securable_type=securable.type.value,
        securable_name=securable.full_name,
        is_owner=bool(owner and owner.owner_principal_id in subject.all_ids),
        privileges=[name for name, result in decisions.items() if result.allowed],
        decisions={
            name: (f"{result.reason}: {result.detail}" if result.detail else result.reason)
            for name, result in decisions.items()
        },
    )
