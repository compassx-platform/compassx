# Layout

`GET /api/v1/portal/config` returns the workspace layout. `PUT /api/v1/portal/config` replaces its sections. Both return `PortalConfigOut`: `id`, `workspace_id`, `workspace_slug`, `sections`, and `updated_at`. `updated_at` falls back to `created_at` when the update time is empty.

The row lives in `apps.portal_configs`. `workspace_id` is unique. `sections` is JSON, stored as JSONB on PostgreSQL. The id is `portal_cfg_` plus 16 hex characters.

## Read

The handler resolves the workspace as the `workspace_id` query, then `guard.workspace_id`, then `default`. It loads `PortalConfig` by that `workspace_id`. When that row is missing and `workspace_slug` was sent, it loads by `workspace_slug`. When both lookups miss, it bootstraps a row and returns that object.

## Bootstrap

`_bootstrap_default_config` builds the first layout from apps and dashboards.

Apps come from the system `App` table, newest `created_at` first. When `workspace_id` is set it filters `App.workspace_id`. Otherwise, when `workspace_slug` is set, it filters `App.workspace_slug`. Each app becomes an item:

- `id` is `item_app_` plus the app id
- `type` is `app`
- `target_id` is the app id
- `title` is the app name
- `icon` is `LayoutGrid` for `react`, `Sparkles` for `streamlit`, and `Code2` for any other `app_type`
- `is_visible` is true
- `order` is the position in that list
- `url` is the app route
- `app_type` and `status` are copied from the app

Those items sit in a section `sec_applications` titled `Applications`, and only when at least one app exists.

Dashboards come from the account `Dashboard` table, newest first, with no workspace filter. Each dashboard becomes an item:

- `id` is `item_dash_` plus the dashboard id
- `type` is `dashboard`
- `target_id` is the dashboard id as a string
- `title` is the dashboard name
- `icon` is `BarChart2`
- `is_visible` is true
- `order` is the position in that list
- `url` and `app_type` are null
- `status` is `draft` when `is_draft` is set, and `published` otherwise

Those items sit in a section `sec_dashboards` titled `Dashboards`, and only when at least one dashboard exists.

When both lists are empty, the layout is a single empty section `sec_applications` titled `Applications`.

The new row uses `workspace_id` or `default`, the given `workspace_slug`, and `created_by_user_id` null. The handler adds it and commits. On failure it rolls back, logs a warning `Could not persist auto-bootstrapped portal config: %s`, and still returns the unsaved object.

## Save

`PUT /api/v1/portal/config` takes `PortalConfigUpdate`. The body is `sections`, a list of `PortalSection`. Each section has `id`, `title`, and `items`. Each item is a `PortalItem`:

- `type` is `app`, `dashboard`, or `external_link`
- `target_id`, `title`, and `order` are required
- `icon`, `url`, `app_type`, and `status` are optional
- `is_visible` defaults to true
- `order` defaults to 0

The handler resolves the workspace the same way as the read. It looks up by `workspace_id` only. A slug match is not used on save. The sections are stored with each section's `.dict()`.

When no row exists, it inserts one with a new `portal_cfg_` id, the resolved workspace id, the query `workspace_slug`, the sections, and `created_by_user_id` null.

When a row exists, it replaces `sections`, sets `workspace_slug` when the query sent one, sets `updated_at` to the current UTC time, and marks `sections` modified so SQLAlchemy writes the JSON.

It then commits and refreshes. A commit failure is not caught.
