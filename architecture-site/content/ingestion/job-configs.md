# Job configs

A job config is one pull: which connection, which path, how to page, where the parameter values come from, and the cron expression. The row is `ingestion_job_config`. It does not store a secret.

## Create and list

`POST /job-configs` requires `connection_id`, `name`, `path_template`, and `schedule_cron`. Defaults are method `GET`, pagination `none`, param source `static`, bronze bucket `compassx-bronze`, and enabled. Empty query, pagination, and param-source objects are stored as `{}`.

`GET /job-configs` lists the workspace, ordered by name. `connection_id` limits the list to that connection. `GET /job-configs/{id}` returns one. A miss is HTTP 404, `Job config {id} not found`.

## Update, enable, disable, delete

`PATCH /job-configs/{id}` updates only name, method, path, query template, body template, pagination, cursor fields, param source, bronze bucket, and cron. A null field is skipped. `is_enabled` is not on this body.

`POST /job-configs/{id}/enable` and `/disable` set `is_enabled` and return HTTP 204. A missing config is 404.

`DELETE /job-configs/{id}` deletes the row. Watermarks and runs cascade with it. The response is HTTP 204. A miss is 404.

## What the templates mean

`path_template` and string values in the query and body templates replace `{param_value}`, `{asset_id}`, and `{cursor}` when a run builds a request. `{asset_id}` is the same replacement as `{param_value}`.

`param_source_type` is `static`, `catalog_query`, or `parent_api`. `pagination_type` is `none`, `offset`, `page`, or `cursor_field`. `cursor_field_path` is a JSONPath read from each page. `cursor_query_param` is the query parameter that receives the current cursor.

`schedule_cron` is stored. This module does not start the cron. A person starts a run with the trigger route.
