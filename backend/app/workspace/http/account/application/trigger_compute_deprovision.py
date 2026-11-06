from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def trigger_compute_deprovision(
    body: Optional[dict] = None,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    """Gracefully migrate compute pods to shared user pool and deprovision compute node pool."""
    from app.services.node_pool_manager import node_pool_manager
    account = db.query(Account).first()
    saved = (getattr(account, "settings", None) or {}).get("compute", {}) if account else {}
    req = body or {}
    pool_name = str(req.get("pool_name") or saved.get("pool_name", "computepool"))
    fallback_pool = str(req.get("fallback_pool") or saved.get("default_pool_name", settings.AZURE_DEFAULT_USER_NODEPOOL))

    # Mark dedicated_pool_enabled as False and is_provisioned as False in account settings
    if account:
        existing = dict(getattr(account, "settings", None) or {})
        comp_existing = dict(existing.get("compute", {}))
        comp_existing["dedicated_pool_enabled"] = False
        comp_existing["is_provisioned"] = False
        existing["compute"] = comp_existing
        account.settings = existing
        db.commit()

    node_pool_manager.trigger_deprovision_compute_nodepool_async(
        pool_name=pool_name, fallback_pool=fallback_pool
    )
    return {"status": "deprovisioning", "message": f"Gracefully migrating pods to '{fallback_pool}' and deprovisioning '{pool_name}'."}
