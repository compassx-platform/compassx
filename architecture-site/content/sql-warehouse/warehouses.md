# Warehouses

A warehouse belongs to one workspace. A request with no workspace sees only rows whose `workspace_id` is null. A request with a workspace sees only that workspace's rows.

The user id is the workspace principal, else the signed-in user's `id` or `sub`. When neither is present the id is `bbbbbbbb-0000-0000-0000-000000000001`. The workspace id is the request workspace, else the `X-Workspace-Id` header, else the `workspace_id` query parameter.

## List, read, create

`GET /api/v1/warehouses` returns the workspace's warehouses, newest first.

`GET /api/v1/warehouses/{id}` is 404 `Warehouse not found` when the id is missing or belongs to another workspace.

`POST /api/v1/warehouses` accepts `name`, `description`, `engine` (default `duckdb`), `is_default`, `config`, and `resource_policy`. The engine must be `duckdb`, `clickhouse`, or `postgres`, or the response is 400 `Unsupported engine '{engine}'.`

The first warehouse in the workspace is the default, and so is a body that sets `is_default`. Creating a default clears `is_default` on the others. The row is inserted, then a pod is started and the row is set to `running` with `runtime_id` and `endpoint_url`.

## Start, stop, default, delete

`POST /api/v1/warehouses/{id}/start` sets status `starting`, starts the pod, then sets `running` with the new runtime id and endpoint.

`POST /api/v1/warehouses/{id}/stop` stops the pod and sets status `stopped`. A status outside `running`, `stopped`, `starting`, `stopping`, and `error` is 400 `Unsupported warehouse status '{status}'.`

`POST /api/v1/warehouses/{id}/set-default` marks that warehouse default and clears the flag on the others in the workspace.

`DELETE /api/v1/warehouses/{id}` deletes the pod, then the row, and returns `{ "deleted": true }`.

## Pod

The runtime id is `wh-` plus the first 16 characters of the warehouse id, with characters other than letters, digits, `_`, and `-` removed.

DuckDB uses image `COMPASSX_DUCKDB_WAREHOUSE_IMAGE`, default `ghcr.io/compassx-platform/compute-duckdb:v0.16.0`, and port 8080. ClickHouse uses `COMPASSX_CLICKHOUSE_WAREHOUSE_IMAGE`, default `clickhouse/clickhouse-server:24.3-alpine`, and ports 8123 and 9000. Any other engine uses `python:3.11-slim`.

Memory and CPU limits come from `resource_policy.max_memory_mb` and `max_threads`. When those are absent the limits are `2Gi` and `2`. Requests stay `512Mi` and `500m`.

On Kubernetes the endpoint is `http://compassx-{runtime_id}.{namespace}.svc.cluster.local:{port}` and a ClusterIP service of that name is created. Elsewhere the endpoint is `http://{compose project}-{runtime_id}:{port}`. Readiness polls `/healthz`, or `/ping` for ClickHouse, for up to 15 seconds. A provision failure is logged and the endpoint is still returned.

## Health

`GET /api/v1/sql-warehouse/health` does not require a signed-in user. It runs `SELECT 1` on the system database. Success is `{ "status": "ok", "postgres": true, "cache": true }`. A database error is `{ "status": "degraded", "postgres": false, "cache": true }`.
