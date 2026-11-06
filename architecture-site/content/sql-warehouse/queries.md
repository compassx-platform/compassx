# Queries

`POST /api/v1/sql/query` runs SQL. The body is `sql`, optional `warehouse_id`, `session_id`, `catalog`, `schema_name`, `source` (default `sql_editor`), and `max_rows` from 1 to 100,000 (default 10,000).

The named warehouse is used when it belongs to the workspace. Otherwise the default warehouse is used: the one with `is_default`, else the one named `default`, else the oldest. When none exists the response is 404 `No active or default warehouse found for this workspace`.

A warehouse that is not `running` is started before the query, the same way as Start.

## Execution

`QueryExecutor.run` hashes `sql`, `max_rows`, `catalog`, and `schema_name`. It then checks the warehouse policy. `resource_policy.max_concurrent_queries`, when set, counts rows in `active_queries`. At the limit the response is 429 `Warehouse '{name}' has reached its concurrent query limit of {n}.`

When the request has no `session_id`, a cached payload for that hash and warehouse is returned and a history row is written with status `succeeded` and `cache_hit` true. The log line is `query_cache_hit` on logger `app.sql_warehouse.query.executor`. An empty cached payload is dropped, so a query that returned no rows is run again. The cache keeps a payload for one hour, and only when the result has rows and at most 10,000 of them.

Otherwise a history row is inserted with status `queued`, an active-query row is registered, status becomes `running`, and the engine adapter runs the SQL. The timeout is `resource_policy.query_timeout_sec`, default 300. `max_threads` and `max_memory_mb` are passed through.

A DuckDB warehouse first builds setup SQL from the catalog plan. When `catalog` is `main`, `temp`, `system`, or `memory`, setup adds `USE "{schema}"` only if a schema was sent. Any other catalog adds `USE "{catalog}"."{schema}"`, or `USE "{catalog}"` when no schema was sent.

Success returns `columns`, `rows`, `rows_returned`, `row_count`, `truncated`, `bytes_scanned`, `duration_ms`, `execution_time_ms`, `query_analysis`, `query_id`, `warehouse_id`, and `cache_hit`. The history row becomes `succeeded`. The log line is `query_completed`. A failure sets the history row to `failed`, logs `query_completed` with status `failed`, and the HTTP response is 400 `{ "error": "Query execution failed", "detail": "..." }`.

DuckDB with an endpoint posts to `{endpoint}/v1/query`. If that connection fails, the adapter logs a warning and runs DuckDB in this process. ClickHouse and Postgres use the warehouse `config`, or the endpoint host when ClickHouse has no host of its own.

## Explain, validate, cancel

`POST /api/v1/sql/explain` uses the named warehouse or the default. The workspace is taken only from the request workspace, not from the header. A missing warehouse is 404 `Warehouse not found`. The body is `{ "plan": ... }`.

`POST /api/v1/sql/validate` parses the SQL with `sqlparse`. The `dialect` field is ignored. Empty SQL is `{ "valid": false, "error": "Empty SQL" }`. Otherwise `{ "valid": true, "statement_count": n }`.

`POST /api/v1/sql/cancel` looks up the active query. A missing one is 404 `Query not found or already completed`. The warehouse is resolved from the request workspace only. The adapter cancel uses `engine_query_id`, or the query id. The history status becomes `cancelled` and the active row is removed. The body is `{ "cancelled": true, "query_id": "..." }`.

## History and result

`GET /api/v1/sql/history` accepts `warehouse_id`, `limit` (default 50, max 500), `offset`, `status`, and `scope` (default `me`). Scope `me` returns that user's rows. Any other scope returns every user. The body is `{ "records", "limit", "offset" }`. Each record includes the SQL, status, engine, source, dashboard and dataset ids, row count, duration, error, cache flag, and analysis. It does not include the stored result payload.

`GET /api/v1/sql/result/{query_id}` is 404 `Query not found` when the row is missing, and 403 `Forbidden` when the row belongs to another user. A stored payload is returned with `query_id`, `cache_hit`, and `query_analysis`. Without a payload the body is `{ "query_id", "status", "message": "Result no longer available. Re-run the query." }`.
