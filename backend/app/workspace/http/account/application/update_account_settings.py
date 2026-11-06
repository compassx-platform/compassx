from __future__ import annotations

def _bind():
    import app.workspace.http.account.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

from app.workspace.http.account.application.get_account_settings import get_account_settings


def update_account_settings(
    body: dict,
    db: Session = Depends(get_account_db),
    _admin: Principal = Depends(require_account_admin),
):
    account = db.query(Account).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    existing = dict(getattr(account, "settings", None) or {})
    for key, value in body.items():
        if isinstance(value, dict) and key in existing and isinstance(existing[key], dict):
            existing[key] = {**existing[key], **value}
        else:
            existing[key] = value

    account.settings = existing
    db.commit()
    db.refresh(account)

    # 1. Apply Airflow webserver on-demand start/stop & scheduler tuning if requested
    if "airflow" in body and isinstance(body["airflow"], dict):
        airflow_body = body["airflow"]
        try:
            from services.airflow.manager import get_airflow_manager
            mgr = get_airflow_manager()

            # Handle webserver enable/disable
            if "webserver_enabled" in airflow_body:
                enable_ws = bool(airflow_body["webserver_enabled"])
                if enable_ws:
                    mgr.start_webserver()
                else:
                    mgr.stop_webserver()

            # Handle scheduler tuning
            dag_dir = airflow_body.get("dag_dir_list_interval")
            min_proc = airflow_body.get("min_file_process_interval")
            procs = airflow_body.get("parsing_processes")
            tuning_prof = airflow_body.get("tuning_profile")
            if any(x is not None for x in [dag_dir, min_proc, procs, tuning_prof]):
                final_dag_dir = int(dag_dir if dag_dir is not None else existing.get("airflow", {}).get("dag_dir_list_interval", 300))
                final_min_proc = int(min_proc if min_proc is not None else existing.get("airflow", {}).get("min_file_process_interval", 120))
                final_procs = int(procs if procs is not None else existing.get("airflow", {}).get("parsing_processes", 2))
                mgr.update_scheduler_tuning(
                    dag_dir_list_interval=final_dag_dir,
                    min_file_process_interval=final_min_proc,
                    parsing_processes=final_procs,
                    tuning_profile=tuning_prof,
                )
        except Exception as exc:
            logger.warning("Could not apply Airflow configuration change: %s", exc)

    # 2. Apply App Node Pool configuration & pod switchover if requested
    if "app_node_pool" in body and isinstance(body["app_node_pool"], dict):
        pool_cfg = body["app_node_pool"]
        try:
            from app.services.node_pool_manager import node_pool_manager
            dedicated = bool(pool_cfg.get("dedicated_pool_enabled", existing.get("app_node_pool", {}).get("dedicated_pool_enabled", False)))
            vm_size = str(pool_cfg.get("vm_size") or existing.get("app_node_pool", {}).get("vm_size") or "Standard_B2s_v2")
            min_count = int(pool_cfg.get("min_count") or 1)
            max_count = int(pool_cfg.get("max_count") or 5)
            auto_scale = bool(pool_cfg.get("auto_scale", True))
            pool_name = str(pool_cfg.get("pool_name") or "apppool")
            default_pool_name = str(pool_cfg.get("default_pool_name") or "systempoolv2")

            if dedicated:
                # Trigger AKS nodepool provision/update in background
                node_pool_manager.trigger_provision_nodepool_async(
                    vm_size=vm_size, min_count=min_count, max_count=max_count, auto_scale=auto_scale
                )
                # Immediately roll over app workloads to target dedicated pool
                target = pool_name
            else:
                # Roll over app workloads to default user pool
                target = default_pool_name

            node_pool_manager.switchover_app_workloads(target_pool=target)
        except Exception as exc:
            logger.warning("Could not apply App Node Pool configuration change: %s", exc)

    # 3. Apply Compute Node Pool configuration if requested
    if "compute" in body and isinstance(body["compute"], dict):
        comp_cfg = body["compute"]
        try:
            from app.services.node_pool_manager import node_pool_manager
            dedicated = bool(comp_cfg.get("dedicated_pool_enabled", existing.get("compute", {}).get("dedicated_pool_enabled", True)))
            vm_size = str(comp_cfg.get("vm_size") or existing.get("compute", {}).get("vm_size") or "Standard_D4ads_v5")
            min_count = int(comp_cfg.get("min_count") if comp_cfg.get("min_count") is not None else 0)
            max_count = int(comp_cfg.get("max_count") or 10)
            auto_scale = bool(comp_cfg.get("auto_scale", True))
            pool_name = str(comp_cfg.get("pool_name") or "computepool")
            default_pool_name = str(comp_cfg.get("default_pool_name") or settings.AZURE_DEFAULT_USER_NODEPOOL)

            if dedicated:
                node_pool_manager.trigger_provision_compute_nodepool_async(
                    pool_name=pool_name, vm_size=vm_size, min_count=min_count, max_count=max_count, auto_scale=auto_scale
                )
            else:
                # Dedicated compute disabled: gracefully move compute pods to default user pool and deprovision AKS compute pool
                node_pool_manager.trigger_deprovision_compute_nodepool_async(
                    pool_name=pool_name, fallback_pool=default_pool_name
                )
        except Exception as exc:
            logger.warning("Could not apply Compute Node Pool configuration change: %s", exc)

    return get_account_settings(db=db, _admin=_admin)
