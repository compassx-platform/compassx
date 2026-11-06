# Apps

An app is a workspace application stored in the system table `apps.apps`. The id is `app_` plus 16 hex characters. The screen is **Apps**. Building and running a dev copy goes through `/api/v1/apps/{app_id}/dev`. The shared Omnigent server is a separate router at `/api/v1/services/omnigent`.

This module does not register an agent tool. There is no Tools page.

## What stays public

`app.routes.app_routes` still defines `router` at prefix `/api/v1/apps` and every handler name. `app.routes.app_dev_routes` still defines its router at prefix `/api/v1/apps/{app_id}/dev`, the request models, `_build_app_sandbox_spec`, `_sync_agent_login`, `_supervise`, `_port_open`, `forward`, and `handle_client`. `services.omnigent.router` still defines `router` and `_error`.

Each handler forwards to one application file. Logs stay on `app.routes.app_routes`, `app.routes.app_dev_routes`, and `services.omnigent.router`.

The `App` model stays in `app.models.app`. `app_runner_service`, `omnigent_dev_service`, `app_manifest_service`, and `OmnigentManager` stay where callers already import them.

## Access

List uses the guard workspace id, or the `workspace_id` query, or the `workspace_slug` query when neither id is set. Get returns HTTP 404 `App '{id}' not found.` and, for another workspace, `App not found in this workspace.` Update, delete, deploy, and runtime changes return HTTP 403 `Cannot modify app from another workspace.`, `Cannot delete app from another workspace.`, or `Cannot deploy app from another workspace.` Deployment reads use `Cannot access app from another workspace.`

Dev routes use `Cannot access app in another workspace.` Live logs and the traffic proxy do not compare the workspace. The proxy has no guard.

## Files

- `app/routes/app_routes.py` — app HTTP facade
- `app/apps/record/application/` — one file per app action
- `app/routes/app_dev_routes.py` — dev studio HTTP facade
- `app/apps/dev/prelude.py` — request models and sandbox spec helper
- `app/apps/dev/application/` — one file per dev action
- `services/omnigent/router.py` — Omnigent server facade
- `services/omnigent/http/application/` — one file per server action
- `services/omnigent/manager.py` — deployment lifecycle

## Pages

- [Records](records.md)
- [Dev studio](studio.md)
- [Omnigent server](omnigent.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
