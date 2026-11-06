# SQL

`POST /api/v1/data-catalog/sql/execute` runs one statement on a saved connection.

The body is `connection_id`, `database`, `sql`, and `limit`. `sql` must be at least one character. `limit` defaults to `1000`, with a minimum of `1` and a maximum of `5000`. A body outside those bounds is HTTP 422.

An unknown connection is HTTP 404 `Connection {id} not found`. A decrypt failure is HTTP 404 `Cannot decrypt stored password – check CATALOG_ENCRYPTION_KEY`.

The statement is wrapped before it is sent:

`SELECT * FROM ({sql}) __q LIMIT {limit + 1}`

A trailing semicolon on `sql` is removed before the wrap. The connection is rolled back after a successful read and after a database error, so the call does not leave an open transaction.

A successful body has `columns`, `rows`, `row_count`, `execution_time_ms`, `truncated`, and `error` null. `columns` are the cursor description names. Each row is a list. Cell values use the same conversion as a table preview. `row_count` is the number of rows returned after the limit. `truncated` is true when the wrapped query produced more than `limit` rows. `execution_time_ms` is rounded to two decimal places.

`psycopg2.Error` does not become HTTP 500. The response is still HTTP 200, with empty columns and rows, `row_count` `0`, `truncated` false, and `error` set to the stripped exception text. `execution_time_ms` is still filled in.

Any other exception after the connection is known, including a failure to open the server, is HTTP 500 and the detail is `str(exc)`.
