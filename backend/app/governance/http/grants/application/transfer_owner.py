from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def transfer_owner(
    payload: OwnerIn,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> OwnerOut:
    """Transfer ownership. Requires MANAGE, which an owner holds implicitly."""
    securable = payload.to_securable()
    try:
        row = service.transfer_ownership(
            db,
            workspace_id=guard.workspace_id,
            securable=securable,
            new_owner_principal_id=payload.owner_principal_id,
            new_owner_principal_type=payload.owner_principal_type,
            actor=guard.principal,
        )
    except PermissionDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except (GovernanceError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return OwnerOut(
        securable_type=row.securable_type,
        securable_name=securable.full_name,
        owner_principal_id=row.owner_principal_id,
        owner_principal_type=row.owner_principal_type,
        assigned_at=row.assigned_at,
    )
