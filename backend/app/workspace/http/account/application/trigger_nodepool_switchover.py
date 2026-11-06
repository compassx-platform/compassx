from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def trigger_nodepool_switchover(
    target_pool: Optional[str] = None,
    _admin: Principal = Depends(require_account_admin),
):
    """Trigger manual/forced rolling switchover of all app pods to the target node pool."""
    from app.services.node_pool_manager import node_pool_manager
    res = node_pool_manager.switchover_app_workloads(target_pool=target_pool)
    return res
