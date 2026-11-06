from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def trigger_compute_provision(
    body: Optional[dict] = None,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    """Explicitly provision or update compute node pool."""
    from app.services.node_pool_manager import node_pool_manager
    account = db.query(Account).first()
    saved = (getattr(account, "settings", None) or {}).get("compute", {}) if account else {}
    req = body or {}
    vm_size = str(req.get("vm_size") or saved.get("vm_size") or "Standard_D4ads_v5")
    min_count = int(req.get("min_count") if req.get("min_count") is not None else saved.get("min_count", 0))
    max_count = int(req.get("max_count") or saved.get("max_count", 10))
    pool_name = str(req.get("pool_name") or saved.get("pool_name", "computepool"))

    # Persist provisioning state to DB
    if account:
        existing = dict(getattr(account, "settings", None) or {})
        comp_existing = dict(existing.get("compute", {}))
        comp_existing.update({
            "dedicated_pool_enabled": True,
            "pool_name": pool_name,
            "vm_size": vm_size,
            "min_count": min_count,
            "max_count": max_count,
            "is_provisioned": True,
        })
        existing["compute"] = comp_existing
        account.settings = existing
        db.commit()

    node_pool_manager.trigger_provision_compute_nodepool_async(
        pool_name=pool_name, vm_size=vm_size, min_count=min_count, max_count=max_count, auto_scale=True
    )
    return {"status": "provisioning", "message": f"Provisioning '{pool_name}' ({vm_size}, Min: {min_count}, Max: {max_count}) initiated."}
