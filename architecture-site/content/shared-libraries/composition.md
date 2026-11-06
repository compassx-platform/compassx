# Composition

`app.config.Settings` reads `.env`, `backend/.env`, and `../.env`. Unknown environment keys are ignored.

Postgres defaults are host `localhost`, port `5432`, user `postgres`, and password `postgres`. `SYSTEM_DB_NAME` defaults to `compassx_account`. `DATA_DB_NAME` defaults to `compassx_system`. A non-empty `SYSTEM_DB_URL` or `DATA_DB_URL` replaces the derived URL. Pool minimum is `10` and pool maximum is `50` for both. `database_url` is `resolved_data_db_url`.

`CATALOG_ENCRYPTION_KEY` is the Fernet key when it is set. Otherwise the key is the URL-safe base64 of SHA-256 of `{PG_PASSWORD}:{SYSTEM_DB_NAME}:catalog-key-v1`.

`APP_RUNNER_MODE` is empty by default. `APP_BASE_DOMAIN` is `compassx.internal`. `APP_DOMAIN_TEMPLATE` is `{slug}.{base_domain}`. Storage defaults are backend `minio`, endpoint `http://localhost:9000`, bucket `compassx`, keys `minioadmin`, and region `us-east-1`. First-boot defaults are account name `CompassX` and slug `default`. Access tokens last `15` minutes. Refresh tokens last `30` days.

## Databases

`app.database` opens two engines at import.

The account engine uses `resolved_system_db_url` and `AccountBase`. The code comment calls this the control-plane database. Startup ensures `SYSTEM_DB_NAME` exists, then runs `SELECT 1`. Success logs `Account (control plane) database connection successful: %s`. It then creates the dashboard table and logs `Account dashboard table verified/created`, or warns `Could not verify/create account dashboard table: %s`. `SKIP_DB_INIT` logs `Account database connection test skipped (SKIP_DB_INIT=True)`. A failure logs `FATAL: Account (control plane) database unavailable:` and raises `RuntimeError` `Account database unavailable ({url}): {error}`. Creating a missing database logs `Auto-created database '%s'`. An existing database logs `Database '%s' already exists` at debug.

The system engine uses `resolved_data_db_url` and `SystemBase`. Success logs `System database connection successful: %s`. It runs `CREATE SCHEMA IF NOT EXISTS apps` and creates the `AppTask` table. A task-table failure logs `Could not auto-create app_tasks table: %s` at debug. `SKIP_DB_INIT` logs `System database connection test skipped (SKIP_DB_INIT=True)`. A failure logs `FATAL: System database unavailable:` and raises `RuntimeError` `System database unavailable ({url}): {error}`.

`get_account_db` yields an account session. `get_system_db` yields a system session. `get_db`, `SessionLocal`, `engine`, `Base`, and `is_db_available` are the system-database names.

## Request dependencies

`get_current_user` returns a fixed administrator. The id is `bbbbbbbb-0000-0000-0000-000000000001`, the email is `vishal@compass.internal`, the org id is `aaaaaaaa-0000-0000-0000-000000000001`, the name is `Vishalkumar Vora`, and `is_account_admin` is true.

`get_platform` returns `request.app.state.platform`. When that is missing it builds a `PlatformContainer` and stores it. `get_service_registry` returns that container's registry. `get_monitoring_resource_manager` returns `monitoring_resource_manager`. `get_runtime_manager` returns `request.app.state.runtime_manager`, or builds one with `SqlRuntimeRepository` when `SystemSessionLocal` exists.
