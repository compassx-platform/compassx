# Settings

Account settings are stored on the account row's `settings` JSON. Workspace settings are stored inside the workspace `storage_config` under `workspace_settings`. Both reads merge saved values over the defaults in the route module.

## Account settings

`GET /api/account/settings` returns `account_id`, `account_name`, `account_slug`, and `settings`. Defaults cover `airflow`, `app_node_pool`, and `compute`. Airflow defaults include `webserver_enabled` false and `tuning_profile` `cost_optimized`. The app pool defaults to name `apppool`, VM `Standard_B2s_v2`, and default pool `systempoolv2`. Compute defaults to pool `computepool`, VM `Standard_D4ads_v5`, min 0, max 10, and `is_provisioned` true.

The read adds live Airflow webserver and scheduler values when the manager answers. A failure logs `Could not query live Airflow webserver and tuning status: %s` at debug and sets `webserver_status` to `stopped` when the webserver is disabled, otherwise `unknown`. Live app-pool and compute-pool status are merged the same way. Failures log `Could not query live node pool status: %s` and `Could not query live compute node pool status: %s`.

`PATCH /api/account/settings` merges the body into the saved JSON and returns the same shape as the GET. An `airflow` object can start or stop the webserver and update scheduler tuning. A failure logs `Could not apply Airflow configuration change: %s`. An `app_node_pool` object provisions the dedicated pool when `dedicated_pool_enabled` is true and switches app workloads to `pool_name`, or to `default_pool_name` when it is false. A failure logs `Could not apply App Node Pool configuration change: %s`. A `compute` object provisions `computepool` when dedicated, or deprovisions it onto `AZURE_DEFAULT_USER_NODEPOOL` when not. A failure logs `Could not apply Compute Node Pool configuration change: %s`.

`POST /api/account/settings/nodepool/switchover` takes optional `target_pool` and returns the node-pool manager result. `GET /api/account/settings/nodepool/status` returns the live app-pool status.

`POST /api/account/settings/compute/provision` saves `dedicated_pool_enabled` true and `is_provisioned` true, then starts provisioning. The response is `{ status: "provisioning", message: "Provisioning '{pool}' ({vm}, Min: {min}, Max: {max}) initiated." }`. `POST .../deprovision` saves both flags false and returns `{ status: "deprovisioning", message: "Gracefully migrating pods to '{fallback}' and deprovisioning '{pool}'." }`. `POST .../switchover` moves compute and notebook pods. `GET .../status` returns the live compute pool.

## Workspace settings

`GET /api/w/{slug}/api/workspace/settings` merges saved `workspace_settings` over the defaults. Defaults include `default_warehouse` `last_selected`, `serverless_interactive_timeout` 9000, PyPI `https://pypi.org/simple`, Python `3.11`, Spark `3.5.0`, and required tags `Environment`, `CostCenter`, and `Project`. A missing workspace is HTTP 404 `Workspace not found`.

`PATCH /api/w/{slug}/api/workspace/settings` requires role `admin` or an account admin. Anyone else gets HTTP 403 `Workspace admin required`. Dict values merge into the existing dict for that key. Other values replace the key. The new map is saved as `storage_config.workspace_settings`, and the response is the merged settings.
