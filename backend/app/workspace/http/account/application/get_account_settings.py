from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def get_account_settings(
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    account = db.query(Account).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    saved = getattr(account, "settings", None) or {}
    merged = {**DEFAULT_ACCOUNT_SETTINGS, **saved}
    for k in ["airflow", "app_node_pool", "compute"]:
        if k in DEFAULT_ACCOUNT_SETTINGS and isinstance(DEFAULT_ACCOUNT_SETTINGS[k], dict):
            merged[k] = {**DEFAULT_ACCOUNT_SETTINGS[k], **saved.get(k, {})}

    # Enrich with live Airflow Webserver and Scheduler Tuning status
    try:
        from services.airflow.manager import get_airflow_manager
        mgr = get_airflow_manager()
        live_status = mgr.get_webserver_status()
        merged["airflow"]["webserver_status"] = live_status.get("status", "stopped")
        merged["airflow"]["webserver_replicas"] = live_status.get("replicas", 0)
        merged["airflow"]["webserver_available_replicas"] = live_status.get("available_replicas", 0)
        merged["airflow"]["webserver_url"] = live_status.get("url")

        live_tuning = mgr.get_scheduler_tuning()
        for tk, tv in live_tuning.items():
            if tk not in saved.get("airflow", {}):
                merged["airflow"][tk] = tv
    except Exception as exc:
        logger.debug("Could not query live Airflow webserver and tuning status: %s", exc)
        merged["airflow"]["webserver_status"] = "stopped" if not merged["airflow"].get("webserver_enabled") else "unknown"

    # Enrich with live App Node Pool status
    try:
        from app.services.node_pool_manager import node_pool_manager
        pool_status = node_pool_manager.get_node_pool_status()
        merged["app_node_pool"] = {**merged.get("app_node_pool", {}), **pool_status}
    except Exception as exc:
        logger.debug("Could not query live node pool status: %s", exc)

    # Enrich with live Compute Node Pool status
    try:
        from app.services.node_pool_manager import node_pool_manager
        comp_status = node_pool_manager.get_compute_pool_status()
        merged["compute"] = {**merged.get("compute", {}), **comp_status}
    except Exception as exc:
        logger.debug("Could not query live compute node pool status: %s", exc)

    return {
        "account_id": str(account.id),
        "account_name": account.name,
        "account_slug": account.slug,
        "settings": merged,
    }
