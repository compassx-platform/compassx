from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def create_grant(
    payload: GrantIn,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> list[GrantOut]:
    """Grant privileges. Idempotent — re-granting returns an empty list."""
    securable = payload.to_securable()
    try:
        rows = service.grant(
            db,
            workspace_id=guard.workspace_id,
            securable=securable,
            principal_id=payload.principal_id,
            principal_type=payload.principal_type,
            privileges=payload.privileges,
            actor=guard.principal,
            expires_at=payload.expires_at,
        )
    except PermissionDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except (GovernanceError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return [_to_grant_out(row) for row in rows]
