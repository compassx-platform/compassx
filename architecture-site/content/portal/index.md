# Portal

The portal is the workspace consumption screen. It stores one sidebar layout per workspace in the system table `apps.portal_configs`, and the screen opens the apps and dashboards named in that layout.

The HTTP surface is `/api/v1/portal`. There are three routes: read the layout, save the layout, and list apps and dashboards that can be added. This module does not register an agent tool. There is no Tools page.

## What stays public

`app.routes.portal_routes` still defines `router` at prefix `/api/v1/portal`, tags `Portal`, and the handler names `get_portal_config`, `update_portal_config`, and `get_available_items`. It also still exposes `_bootstrap_default_config`.

Each handler forwards to one application file. The bootstrap warning stays on the logger `app.routes.portal_routes`.

`PortalConfig` stays in `app.models.portal_config`. The request and response models stay in `app.schemas.portal_config`.

## Access

Every route depends on `get_guard`. The layout routes take an optional `workspace_id` query and an optional `workspace_slug` query. When `workspace_id` is omitted, they use `guard.workspace_id`, and when that is also missing they use the string `default`.

The available-items route uses `workspace_id` or `guard.workspace_id` and does not substitute `default`. Dashboards on both the bootstrap and the available-items route are every row in the account `dashboards` table. They are not filtered by workspace.

`Guard` has no `user_id` attribute, so `created_by_user_id` is stored as null.

## Files

- `app/routes/portal_routes.py` — HTTP facade
- `app/portal/prelude.py` — shared imports and the pinned logger
- `app/portal/application/get_portal_config.py` — read and bootstrap
- `app/portal/application/update_portal_config.py` — save
- `app/portal/application/get_available_items.py` — candidate apps and dashboards
- `app/models/portal_config.py` — `apps.portal_configs`
- `frontend/src/modules/portal` — screen, drawer, and API hooks
- `frontend/src/components/layout/AppShell.tsx` — portal sidebar

## Pages

- [Layout](layout.md)
- [Available items](available-items.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
