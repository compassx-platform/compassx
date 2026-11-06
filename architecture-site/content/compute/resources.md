# Resources

A compute resource is one row in `compute.compute_resources`. The id is the first 8 hex characters of a UUID. `runtime` is `spark`, `flink`, `ray`, or `duckdb`. `profile` is `local`, `cloud-xs`, `cloud-s`, `cloud-l`, or `gpu`. `desired_status` is `stopped` unless the create path asked to start it. `extra_env` is stored as a JSON string.

The deployment name is `compassx`, then a workspace slug of at most 20 characters, then a name slug of at most 25 characters, then the resource id, joined by hyphens. Characters outside letters, digits, `_`, and `-` become `-`.

Lookups filter by workspace when the request has one. With no workspace id they filter `workspace_id == None` and the caller's `user_id`. A missing row raises `ValueError` `Resource not found: {id}`, which the route returns as HTTP 404 `{"error":"NotFound","message":"...","code":404}`.

## Create

`POST /resources` is HTTP 201. The body is `ComputeResourceRequest`: name, runtime, profile, optional description, custom image, and extra env. The route passes the signed-in user as both `user_id` and `created_by`, plus the workspace id and the workspace slug or name.

`create_resource` resolves the profile for `COMPASSX_ENV`. An unknown or unavailable profile raises `ProfileNotAvailableError`, which is not a `ValueError`, so the route returns HTTP 500 `InternalError`. A `ValueError` returns HTTP 400 `InvalidRequest`. Any other exception logs `Error creating compute resource` and returns HTTP 500 `InternalError`.

The row is committed before start. The HTTP create path does not set `auto_start`, so `desired_status` is `stopped`. The log line is `Created compute resource: {id} for user {user}`.

## Update

`PUT /resources/{resource_id}` requires `USE_COMPUTE`. DuckDB with a profile other than `local`, `cloud-xs`, or `cloud-s` raises `ValueError` `DuckDB is only valid with profiles: local, cloud-xs, cloud-s`, which is HTTP 400 `InvalidRequest`.

If `desired_status` was `running`, the service stops the runtime, writes the new fields, then starts it again. A stop or start failure is a warning and the row is still saved. The warnings are `Could not stop resource {id} before update: {error}` and `Could not restart updated resource {id}: {error}`.

## List and status

`GET /resources` returns resources with live status, then keeps a row when it is the default or the caller has `BROWSE`. A failure logs `Error listing compute resources` and returns HTTP 500 `InternalError`.

`GET /resources/{resource_id}` requires `BROWSE`. A missing row is HTTP 404 `NotFound`. Other failures log `Error getting compute resource` and return HTTP 500.

When the platform flag is on and a runtime manager is injected, status comes from the platform runtime. Otherwise status comes from the Kubernetes deployment and pod. A status lookup that fails logs `Unable to get status for compute resource {id}: {error}` and the row is still returned with phase `Unknown` and message `Runtime status unavailable; check the compute backend connection.`

## Start and stop

`POST /resources/{resource_id}/start` is HTTP 201. It records activity with the sandbox reaper, then starts the runtime. The JSON is `job_id`, `runtime_id`, `deployment_name`, `pod_name` null, and `status` `Pending`. `desired_status` becomes `running`. The platform log is `Started platform runtime for resource: {id}`. The Kubernetes log is `Started deployment for resource: {id} (job_id={job})`.

`POST /resources/{resource_id}/stop` requires `USE_COMPUTE`. On the platform path it stops the runtime and sets `desired_status` to `stopped`. On the Kubernetes path it scales the deployment to 0. If that fails and a pod name exists, it stops that job. If neither works it raises `ValueError` `No deployment found for resource: {id}`, which is HTTP 404 `NotFound`. Success returns `{"stopped": true, "resource_id": "..."}`.

## Delete

`DELETE /resources/{resource_id}` requires `MANAGE`, including on the default. It deletes the platform runtime or the Kubernetes job, then deletes the row. A missing runtime is ignored. The success body is `{"deleted": true, "resource_id": "..."}`. The log line is `Deleted compute resource: {id}`.

## Serverless ensure

`POST /resources/serverless/ensure` accepts a body or query `notebook_id` and `notebook_name`. If the notebook already has `last_compute_resource_id` and that row exists, the service starts it when `desired_status` is not `running` and returns that status. Otherwise it creates a DuckDB resource with the resolved default profile and starts it. A failure logs `Error ensuring serverless compute resource` and returns HTTP 500 `InternalError`.

## Metrics

`GET /resources/{resource_id}/metrics?range=15m|1h|6h|24h` requires `BROWSE`. The default range is `15m`. Any other range is rejected by the query pattern. A missing resource is HTTP 404 `NotFound`. Other failures log `Error fetching compute resource metrics` and return HTTP 500. If the stored profile cannot be resolved, the series uses the local `local` profile.

## Default for a workspace

`ensure_workspace_default_resources` runs at startup and when a workspace is created. If the workspace has no compute row, it creates one named `default`, runtime DuckDB, `is_default` true, and starts it. The description is `Auto-created default DuckDB compute.` The log line is `No compute resources found for workspace {id}. Creating default DuckDB compute...`. If any compute row already exists, it does not create another. The same function creates a default DuckDB SQL warehouse when the workspace has none. That warehouse row belongs to SQL warehouse.

## Reconciliation

`reconcile_runtime_states` loads rows whose `desired_status` is `running`. If the platform runtime or the deployment is missing, stopped, or scaled to zero, it starts the resource again. Each start logs `Compute startup reconciliation: auto-starting compute resource {id} ({name})`. The summary log is `Compute startup reconciliation checked {n} running resource(s); auto-started {n}`.
