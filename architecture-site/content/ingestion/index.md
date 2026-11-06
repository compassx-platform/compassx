# Ingestion

Product module. Pull-based API ingestion: a connection holds an endpoint and a secret, a job config says how to call it, and a run writes the response into bronze.

The HTTP router is `app.ingestion.routes.router` at `/api/v1/workspaces/{workspace_id}/ingestion`. Every route requires a signed-in user. The public functions stay importable from `app.ingestion.connections`, `app.ingestion.job_configs`, `app.ingestion.watermarks`, `app.ingestion.observability`, and `app.ingestion.execution`. Each function forwards to one application type.

This module does not expose a tool.

## Code

- `backend/app/ingestion/routes.py` — HTTP edge. It maps `ValueError` to 404 or 400 and keeps the background-run log on logger `app.ingestion.routes`.
- `backend/app/ingestion/connection/` — create, read, update, rotate, delete, and secret resolution. The shared lookup is `connection/repository.py`.
- `backend/app/ingestion/job_config/` — job config actions. The shared lookup is `job_config/repository.py`.
- `backend/app/ingestion/watermark/` — read, advance, and reset. The reset log stays on logger `app.ingestion.watermarks`.
- `backend/app/ingestion/run/application/` — list and read runs, resolve param values, fetch one param, and finish a run. Executor logs stay on logger `app.ingestion.execution`.
- `backend/app/ingestion/infrastructure/` — secret box, token bucket, HTTP retry, bronze writes, templates, and JSONPath.
- `backend/app/ingestion/models.py` and `schemas.py` — the system-database tables and the request models. There is no second domain model.

## Owns

System database tables `credential_secret`, `ingestion_connection`, `ingestion_job_config`, `ingestion_watermark`, `ingestion_run`, and `ingestion_run_item`. Page bodies are objects in the `compassx-bronze` bucket, not rows.

## Calls

Secret resolution stays inside this module. A run calls `app.storage.backend.get_default_backend` to write bronze, and falls back to a local file when that call fails. A `catalog_query` param source imports `app.catalog.services.query_catalog_values`. When that import fails, the run logs `catalog_query param source: catalog service not available, returning __none__` and continues with the sentinel param `__none__`.

## Topics

- [Connections](connections.md)
- [Job configs](job-configs.md)
- [Runs](runs.md)
- [Screen](screen.md)

## Test cases

[Test cases](test-cases.md) are the end-to-end checks for this module.
