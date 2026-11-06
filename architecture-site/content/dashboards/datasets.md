# Datasets

A dataset is one object in the document's `datasets` list. It has an `id`, a `dashboardId`, optional `sql`, optional `schema`, and optional `warehouse_id`. Query, schema, export, and field values all look the dataset up by scanning every dashboard. The caller must `BROWSE` the dashboard that contains it. A dashboard they cannot browse is skipped, so a hidden id and a missing id both return 404 `Dataset not found`.

SQL runs on the SQL warehouse. The request's `x-session-id` is the session. The signed-in user is recorded as the runner. `source` is `dashboard`. When the body or dataset names a warehouse, that warehouse must belong to the workspace or the response is 404 `Warehouse not found`. When none is named, the first warehouse with status `running` is used. If none is running, the response is 400 `No running SQL warehouse is available for dashboard queries.`

`:name` placeholders are replaced with SQL literals in this process. The warehouse receives text, not a parameter list. A parameter name must match `[A-Za-z_][A-Za-z0-9_]*` or the response is 400 `Invalid parameter name: {name}`. Strings are quoted and a single quote is doubled. `None` is `NULL`. Booleans are `TRUE` and `FALSE`. Numbers use their Python repr. A list becomes a comma-separated list of literals.

## Query

`POST /api/v1/dashboards/datasets/{datasetId}/query` and the same path as `GET` (the GET is hidden from the OpenAPI schema). The body may include `params`, `filters`, `sql`, and `warehouse_id`.

A non-empty `sql` override is allowed only when the caller has `EDIT` on the owning dashboard. Otherwise the saved dataset SQL is used. Empty SQL is 400 `Dataset has no SQL defined`.

Success is `{ columns, rows, rowCount, executionMs }`. `rowCount` prefers `row_count`, then `rows_returned`, then the length of `rows`. `executionMs` prefers `execution_time_ms`, then `duration_ms`, then 0. Any other failure is 400 `Query error: {exception}`.

## Schema

`GET /api/v1/dashboards/datasets/{datasetId}/schema` returns the stored `schema` when the dataset has one. Otherwise it runs `SELECT * FROM ({sql}) _q LIMIT 0` and returns `{ name, type: "unknown" }` for each column. Empty SQL, or a query that fails, returns `[]`.

## Export

`GET /api/v1/dashboards/datasets/{datasetId}/export?format=csv|tsv|excel` runs the saved SQL with a cap of 100,000 rows. `csv` and `tsv` are `text/plain` attachments named `dataset.csv` and `dataset.tsv`. `excel` needs `openpyxl`; if it is missing the response is 500 `openpyxl not installed`. The workbook is `dataset.xlsx`.

## Field values

`GET /api/v1/dashboards/datasets/{datasetId}/field-values?field=` returns up to 1,000 distinct non-null values. The field is an identifier and must match `[A-Za-z_][A-Za-z0-9_ ]*`, or the response is 400 `Invalid field name`. The query is `SELECT DISTINCT "{field}" FROM ({sql}) _q WHERE "{field}" IS NOT NULL ORDER BY 1 LIMIT 1000`. Empty SQL returns `[]`.
