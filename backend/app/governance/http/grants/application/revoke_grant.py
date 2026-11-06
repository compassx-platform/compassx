from __future__ import annotations

def _bind():
    import app.governance.http.grants.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def revoke_grant(
    payload: RevokeIn,
    guard: Guard = Depends(get_guard),
    db: Session = Depends(get_system_db),
) -> dict:
    """Revoke privileges.

    POST rather than DELETE because the target is a (principal, securable,
    privileges) triple that does not fit a path, and because a DELETE with a
    body is unreliably supported by proxies.
    """
    securable = payload.to_securable()
    try:
        removed = service.revoke(
            db,
            workspace_id=guard.workspace_id,
            securable=securable,
            principal_id=payload.principal_id,
            privileges=payload.privileges,
            actor=guard.principal,
        )
    except PermissionDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from None
    except (GovernanceError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return {"revoked": removed}
