from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_compute_status(
    _admin: Principal = Depends(require_account_admin),
):
    """Return live compute node pool status, cluster pools, and compute workloads."""
    from app.services.node_pool_manager import node_pool_manager
    return node_pool_manager.get_compute_pool_status()
