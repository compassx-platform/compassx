# Connections

Saved connections live in `catalog_connections`. Columns are `id`, `name`, `host`, `port`, `username`, `password_enc`, `default_database`, `created_at`, and `updated_at`. Port defaults to `5432`. The default database defaults to `postgres`. `password_enc` is Fernet ciphertext from `settings.catalog_fernet_key`. When `CATALOG_ENCRYPTION_KEY` is set, that value is the key. Otherwise the key is derived from `PG_PASSWORD`, `SYSTEM_DB_NAME`, and the suffix `catalog-key-v1`.

`ConnectionResponse` returns id, name, host, port, username, default database, and the two timestamps. It does not return `password` or `password_enc`.

## Create, list, read, update, delete

`GET /api/v1/data-catalog/connections` returns every row ordered by `created_at`.

`POST /api/v1/data-catalog/connections` creates a row and answers HTTP 201. The body needs `name`, `host`, `username`, and `password`. Each of those must be at least one character. `name`, `host`, and `username` are at most 255 characters. `port` is `1` through `65535`, default `5432`. `default_database` is at most 255 characters, default `postgres`. The stored password is `encrypt_password` of the submitted password. A missing field or a value outside those bounds is HTTP 422.

`GET /api/v1/data-catalog/connections/{conn_id}` returns one row. An unknown id is HTTP 404 `Connection not found`.

`PUT /api/v1/data-catalog/connections/{conn_id}` changes only the fields that are present. A new `password` is encrypted and stored. An omitted password leaves `password_enc` as it is. An unknown id is HTTP 404 `Connection not found`.

`DELETE /api/v1/data-catalog/connections/{conn_id}` deletes the row and answers HTTP 204 with an empty body. An unknown id is HTTP 404 `Connection not found`.

## Test

`POST /api/v1/data-catalog/connections/test` opens a PostgreSQL connection from the body. It does not read or write `catalog_connections`. The body needs `host`, `username`, and `password`. `port` defaults to `5432`. `database` defaults to `postgres`.

The driver call uses `connect_timeout` `10` and `statement_timeout` `30000`. The probe statement is `SELECT version()`.

Success is `{"success": true, "message": "Connection successful", "server_version": version}`. `psycopg2.OperationalError` is `success` false, `message` the exception text, and `server_version` null. Any other exception is `success` false and `message` `Unexpected error: {exception}`.

## Decrypt

Browsing and SQL decrypt `password_enc`. A bad token logs `Failed to decrypt connection password: %s` at error on `app.data.services.data_catalog_service` and raises `Cannot decrypt stored password – check CATALOG_ENCRYPTION_KEY`. The route turns that `ValueError` into HTTP 404 with that text.
