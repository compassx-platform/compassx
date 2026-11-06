# Available items

`GET /api/v1/portal/available-items` lists apps and dashboards the customize drawer can pin. It returns `PortalAvailableItemsResponse` with `apps` and `dashboards`. It does not read or write `portal_configs`.

The workspace is the `workspace_id` query, or `guard.workspace_id` when that query is omitted. This route does not fall back to `default`.

When that workspace id is set, apps are filtered with `App.workspace_id`. When it is missing and `workspace_slug` was sent, apps are filtered with `App.workspace_slug`. When both are missing, every app is returned. Apps are ordered by `created_at` descending.

Each app is an `AvailableAppItem`: `id`, `name`, `slug`, `description`, `app_type`, `status`, and `route`.

Dashboards are every row in the account `Dashboard` table, newest first, with no workspace filter. Each one is an `AvailableDashboardItem`:

- `id` is the dashboard id as a string
- `name` is the dashboard name
- `description` is always null
- `is_draft` is the boolean value of `is_draft`
- `published_at` is copied from the row

The customize drawer calls this route with `workspace_slug` only. The hook waits until a workspace slug exists, caches the result for 15 seconds, and sends the bearer token when one is stored.
