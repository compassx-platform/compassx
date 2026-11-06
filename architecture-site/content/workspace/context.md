# Context

`WorkspaceMiddleware` runs for HTTP requests. `OPTIONS` is passed through. The slug is taken from the path `/w/{slug}` or `/api/w/{slug}`, then from the headers `x-workspace-slug`, `x-workspace-id`, or `workspace-id`, then from the query `workspace` or `workspace_id`. When none of those is present and the request has a token, the middleware asks for a default workspace. A path with no slug and no token continues with no workspace context.

`resolve_workspace_context` is also what WebSocket callers use. The account database must be configured, or it raises HTTP 503 `system database not available`. A slug that is a UUID matches `slug` or `id`. Any other slug matches `slug` only. A missing workspace is HTTP 404 `workspace not found`. A status other than `active` is HTTP 403 `workspace unavailable`. No token is HTTP 401 `missing auth token`.

The token is accepted in three ways, in order. A user-manager access token whose user is `active` supplies the user id, and account role `account_admin` sets `is_account_admin`. Otherwise a `WpSession` whose hash matches and has not expired supplies `principal_id`. Otherwise an app workload identity matches `workspace_identity.identity_id`, or `id_app_` plus the first 12 lowercase letters and digits of the app id. That caller gets role `workspace_developer` unless the identity names another role. A lookup error logs `Error resolving workload identity %s: %s`.

An account admin with no earlier role is `workspace_admin`. Anyone else needs a `WorkspaceMembership` or a `UmWorkspaceRoleAssignment` on that workspace. Neither is HTTP 403 `not a member of this workspace`. No recognized token is HTTP 401 `invalid or expired token`.

The context stores `workspace_id`, `workspace_slug`, `workspace_name`, `principal_id`, `principal_role`, and `is_account_admin` on `request.state.workspace`.

An explicit slug that fails returns JSON `{"error": "<message>"}`. A failure while inferring the default slug is ignored.

## Catalog visibility on the same router

`GET /api/w/{slug}/api/workspace` returns id, name, slug, status, url, `current_user_role`, and `is_account_admin`.

`GET /api/w/{slug}/api/catalog` lists `WorkspaceCatalog` rows for the workspace's account. `GET .../catalog/{name}/schemas` returns schema id and name. A missing catalog is HTTP 404 `Catalog not found`. `GET .../catalog/{name}/{schema}/objects` returns objects that are `global` or whose `home_workspace_id` is this workspace. Optional query `object_type` filters `object_type`. A missing schema is HTTP 404 `Schema not found`.

`POST .../catalog/objects/{object_id}/publish` sets `visibility` to `global` and clears `home_workspace_id`. A missing object is HTTP 404 `Object not found`. A different home workspace is HTTP 403 `Object belongs to a different workspace`. An object that is already global is HTTP 400 `Object already published`. The caller needs object privilege `PUBLISH`, schema privilege `MANAGE`, or `is_account_admin`. Otherwise the response is HTTP 403 `PUBLISH privilege required`. The body is `{ status: "published", object_id }`.

## First boot

`FirstBootRunner.run` skips when any account row exists and logs `FirstBoot: account already exists — skipping`. An empty database creates an account from `ACCOUNT_NAME` or `CompassX`, slug `ACCOUNT_SLUG` or `default`, and an admin principal. Missing `ADMIN_EMAIL` or `ADMIN_PASSWORD` logs the dev-default warning and uses `admin@compass.internal` and `Admin@123456`. It also creates catalog `system`, type `foreign_postgres`, and schema `public`. Success logs `FirstBoot: complete — account '%s', admin '%s', system catalog registered`.
