# Runs

A run is one execution of a job config. The summary row is `ingestion_run`. One `ingestion_run_item` is one parameter value. A watermark is the last successful cursor for that job and parameter.

## Trigger

`POST /job-configs/{id}/trigger` loads the job. A missing job is HTTP 404. A disabled job is HTTP 400, `Job config is disabled. Enable it before triggering.`

The route then inserts an `ingestion_run` with status `running` and returns that id immediately as `TriggerOut`. `status` is `running`. `message` is `Run enqueued. Poll GET /runs/{run_id} for status.`

The background task opens a new system session and calls `execute_run`. That call inserts a second `ingestion_run` and does the fetch. The id in the trigger response stays the first row. A background failure logs `Background execute_run failed for run %s: %s` at error on logger `app.ingestion.routes`, with the traceback.

`execute_run` can also be called with an optional `airflow_dag_run_id`. That value is stored on the run the executor creates.

## Parameter values

`static` uses `param_source_config.values`. An empty list becomes one value, `__none__`.

`catalog_query` calls `query_catalog_values` with `catalog_object_type` default `asset`, `filter`, and `value_field` default `external_id`. An import failure returns `__none__` after the warning above.

`parent_api` GETs `base_url` plus `path_template`, using the connection's auth and rate limit, then reads `response_list_path` (default `$[*]`) and `value_field` (default `id`). A failure logs `parent_api param resolution failed: %s` at error and returns `__none__`.

Any other source logs `Unknown param_source_type=%s, defaulting to __none__` at warning.

## One parameter

Workers are capped by the connection's `max_concurrency`. Each worker shares one token bucket for that connection, refilled at `rate_limit_rps` (at least 0.1).

Auth headers are `X-API-Key` unless `auth_config.header_name` is set, `Authorization: Bearer …` for a bearer token, or `Authorization: Basic …` for basic auth using `auth_config.username`. `api_key_query` adds `param_name` (default `api_key`) to the query. Default headers are added after that.

The request URL is the base URL plus the rendered path. Offset pagination sends `offset` and `limit` unless `offset_param` and `limit_param` say otherwise, page size default 100. Page pagination sends `page` and `page_size` unless renamed. A cursor is sent on `cursor_query_param` when one is stored. POST sends the rendered body. The timeout is 30 seconds.

HTTP 200 stores the JSON, or the text when the body is not JSON. HTTP 429 retries up to 5 times. HTTP 5xx retries up to 3 times. The wait is `Retry-After` when it is a number, otherwise exponential from 1 second plus jitter, capped at 60 seconds. The log is `HTTP 429 — backoff attempt %d` or `HTTP %s — backoff attempt %d` at warning. Any other 4xx fails immediately. The page cap is `INGESTION_MAX_PAGES`, default 500.

Each page is written to `compassx-bronze/{workspace}/ingestion/{job}/{param}/{run}/page_{n}.json`. The returned path looks like `cx://compassx-bronze/...`. A storage failure writes the same relative path under `BRONZE_LOCAL_ROOT` (default `/tmp/bronze`) and logs `Bronze written (local fallback): %s` at debug. A list body counts as that many rows. Any other body counts as one row. After the last page, `_manifest.json` is written beside the pages.

Offset and page loops stop when a page has fewer rows than the page size. `cursor_field` continues while `pagination_config.next_cursor_path` yields a value, and that value becomes the cursor for the next request. `cursor_field_path` updates the watermark cursor from the page. A bad JSONPath logs `JSONPath extraction failed (path=%s): %s` at warning and leaves the cursor unchanged.

On success the item status is `succeeded` and the watermark is upserted for `(job_config_id, param_value)` with the cursor, the time, and this run id. The watermark advances only after that success. On failure the item status is `failed`, `error_message` is the exception trimmed to 1000 characters, and the watermark stays where it was. The log is `execute_single_param failed: job_config=%s param=%s: %s` at error, with the traceback.

## Finish and read

When every item succeeded, the executor's run status is `succeeded`. When every item failed, it is `failed`. Otherwise it is `partial`. Counts, bytes, and rows are summed. `error_summary` is the first three item errors joined by `; `. The log is `Run %s finished: status=%s params=%d succeeded=%d failed=%d` at info.

`GET /job-configs/{id}/runs` returns up to `limit` runs, default 50, maximum 500, newest first. `status` filters the list. `GET /runs/{id}` returns one run. A miss is HTTP 404, `Run {id} not found`. `GET /runs/{id}/items` returns items ordered by start time, with an optional `status` filter. These reads do not check the workspace id on the row.

## Reset a watermark

`POST /job-configs/{id}/watermarks/reset` deletes watermark rows for that job. `param_value` set deletes that parameter only. `param_value` null deletes every parameter. The response is HTTP 204. The log is `Watermark reset: job_config_id=%s param_value=%s` at info, and a null parameter is logged as `*`. The next successful run starts without the deleted cursor.
