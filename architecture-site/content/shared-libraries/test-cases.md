# Test cases

These checks confirm the shared import paths and the composition behavior. Each case says what you do and what you should see.

## Old route imports

Import `router` from `app.routes.agent_routes`, `app.routes.notebook_routes`, `app.routes.dashboard_routes`, and `app.routes.data_catalog_routes`.

Each import should succeed. The data-catalog router prefix should be `/api/v1/data-catalog`.

## Legacy catalog patch path

Call `list_connections` on `app.services.data_catalog_service`.

The call should be handled by `app.data.services.data_catalog_service`. A unit test that patches `app.services.data_catalog_service._conn_from_record` should still affect database listing.

## Active mode

Leave `APP_RUNNER_MODE` empty on a machine with no Docker socket and no Kubernetes host.

`IngressService.get_active_mode` should return `local`. `DriverFactory.get_app_driver()` should return `LocalAppDriver`.

Set `APP_RUNNER_MODE` to `kubernetes`.

`get_active_mode` should return `kubernetes`, and the factory should return `KubernetesAppDriver`.

## Preview URL

Call `preview_url_from_endpoints` with endpoints `{"8080": "http://localhost:8080", "9201": "http://localhost:9201"}` and fallback `http://fallback`.

The result should be `http://localhost:8080/`.

## Token helper

Call `decode_access_token` from `app.services.user_management_service` with the text `not-a-jwt`.

The result should be `None`.

## Databases

Start the API with Postgres stopped and `SKIP_DB_INIT` left false.

The process should raise `RuntimeError` and the log should contain `FATAL: Account (control plane) database unavailable:` or `FATAL: System database unavailable:`.

Start the API with both databases reachable.

The log should contain `Account (control plane) database connection successful:` and `System database connection successful:`. `GET /healthcheck` should return `{"status": "ok"}`.

## Fixed user

Call a route that depends on `get_current_user`.

The user id should be `bbbbbbbb-0000-0000-0000-000000000001` and the email should be `vishal@compass.internal`.
