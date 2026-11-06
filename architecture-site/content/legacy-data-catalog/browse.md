# Browse

Browse reads a live PostgreSQL server through a saved connection. An unknown connection raises `Connection {id} not found`. The route returns that text as HTTP 404. Any other exception from the driver is HTTP 500 and the body detail is `str(exc)`.

The password is decrypted and the connection uses the record's host, port, and username. Database list uses `default_database`. Schema and table calls use the database in the path.

## Databases

`GET /api/v1/data-catalog/{conn_id}/databases` returns `{"databases": [{"name", "owner"}]}`.

The query is `pg_catalog.pg_database` where `datistemplate` is false, ordered by `datname`. `name` is `datname`. `owner` is `pg_get_userbyid(datdba)`.

## Schemas

`GET /api/v1/data-catalog/{conn_id}/databases/{database}/schemas` returns `{"schemas": [{"name", "owner"}]}`.

The query reads `information_schema.schemata`. It drops `pg_catalog`, `information_schema`, and `pg_toast`. It also drops names that start with `pg_temp_` or `pg_toast_temp_`. Results are ordered by `schema_name`. `owner` is `schema_owner`.

## Tables

`GET /api/v1/data-catalog/{conn_id}/databases/{database}/schemas/{schema}/tables` returns `{"tables": [{"name", "schema_name", "table_type", "row_estimate"}]}`.

The query joins `information_schema.tables` to `pg_stat_user_tables` on schema and table name. `table_type` is the information-schema value, such as `BASE TABLE` or `VIEW`. `row_estimate` is `n_live_tup`. Rows are ordered by `table_type`, then `table_name`. The schema name is a bound parameter.

## Preview

`GET /api/v1/data-catalog/{conn_id}/databases/{database}/schemas/{schema}/tables/{table}/preview` returns columns, rows, `total_rows`, and `truncated`.

`limit` defaults to `100`. The smallest value is `1` and the largest is `500`. A value outside that range is HTTP 422.

Columns come from `information_schema.columns` for that schema and table, ordered by `ordinal_position`. Each column has `name`, `data_type`, `is_nullable`, `column_default`, `ordinal_position`, and `character_maximum_length`. `is_nullable` is true when the information-schema value is `YES`.

`total_rows` is `reltuples` from `pg_class` where `relname` is the table name. A missing estimate is `0`.

The sample is `SELECT * FROM "{schema}"."{table}" LIMIT {limit}`. A double quote in the schema or table name is doubled before it is placed in the identifier. `truncated` is true when the returned row count is greater than or equal to `limit`.

A cell that is null, a number, a boolean, or a string is returned as that value. A dict or list is `json.dumps` with `ensure_ascii` false. Every other value is `str(value)`.
