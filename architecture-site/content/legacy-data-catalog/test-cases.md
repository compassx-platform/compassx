# Test cases

These are checks against `/api/v1/data-catalog`. The Catalog screen at `/data-catalog` is a different module. Each case says what you do and what you should see.

## Save a connection

`POST /api/v1/data-catalog/connections` with name, host, port `5432`, username, password, and default database `postgres`.

The status should be 201. The JSON should include an integer `id` and the name, host, port, username, and default database. It should not include `password` or `password_enc`.

`GET /api/v1/data-catalog/connections` should list that connection. `GET /api/v1/data-catalog/connections/{id}` should return the same fields.

## Reject a bad body

`POST /api/v1/data-catalog/connections` with an empty name, or with port `0`.

The status should be 422.

## Update and delete

`PUT /api/v1/data-catalog/connections/{id}` with a new name and no password.

The name should change. A later browse of that connection should still decrypt the original password.

`PUT` and `DELETE` for id `999999` should be HTTP 404 `Connection not found`.

`DELETE /api/v1/data-catalog/connections/{id}` for a real id should be HTTP 204. A following GET of that id should be HTTP 404 `Connection not found`.

## Test a host

`POST /api/v1/data-catalog/connections/test` with a reachable PostgreSQL host, port, username, password, and database.

You should see `success` true, `message` `Connection successful`, and `server_version` set to the server's version string.

Repeat the call with a closed port.

You should see `success` false and `server_version` null. The message should be the driver's connection error, or `Unexpected error:` followed by the exception.

## Browse

Using a saved connection, `GET /api/v1/data-catalog/{id}/databases`.

You should see `databases`, each with `name` and `owner`. Template databases should be absent.

`GET /api/v1/data-catalog/{id}/databases/{database}/schemas`.

You should see schemas. `pg_catalog`, `information_schema`, and `pg_toast` should be absent.

`GET /api/v1/data-catalog/{id}/databases/{database}/schemas/{schema}/tables`.

You should see `name`, `schema_name`, `table_type`, and `row_estimate`.

`GET` the same table's `preview` with `limit` `2`.

You should see `columns`, at most two `rows`, `total_rows`, and `truncated` true when the table has at least two rows. A JSON column cell should be a JSON string.

`GET /api/v1/data-catalog/999999/databases` should be HTTP 404 `Connection 999999 not found`.

## Run SQL

`POST /api/v1/data-catalog/sql/execute` with the connection id, a database, `sql` `SELECT 1 AS n`, and `limit` `10`.

You should see column `n`, one row, `row_count` `1`, `truncated` false, and `error` null. `execution_time_ms` should be a number.

Send a statement the server rejects.

The status should stay 200. `columns` and `rows` should be empty, `row_count` should be `0`, `truncated` should be false, and `error` should contain the database message.

Send `limit` `6000`.

The status should be 422.
