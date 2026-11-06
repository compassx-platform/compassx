# Workspace

Workspace is the tenant boundary. It stores accounts, workspaces, legacy principals, and legacy memberships on the account database. A request under `/w/{slug}` is placed in one workspace by middleware before the route runs.

`main.py` includes three routers from `app.workspace`. Auth is `/api/auth`. Account admin is `/api/account`, and the same router is included again with prefix `/api/v1`, so those paths also exist at `/api/v1/api/account`. Workspace-scoped routes are `/api/w/{slug}/api`. This module does not register an agent tool. There is no Tools page.

People, invites, and user-manager membership stay in Identity. Workspace does not move out of this process, and it keeps sharing the account database with Identity.

## What stays public

`app.workspace.auth_routes`, `account_routes`, and `workspace_routes` still define `router` and the same handler names. `create_workspace` stays importable from `app.workspace.account_routes` and is still async. `app.routes.workspace_routes` still re-exports the workspace router.

Each handler forwards to one application file. Loggers stay `app.workspace.auth_routes`, `app.workspace.account_routes`, and `app.workspace.workspace_routes`.

`resolve_workspace_context`, `WorkspaceContext`, `WorkspaceAuthError`, and `WorkspaceMiddleware` stay in `app.workspace.middleware`. `get_current_principal` and `require_account_admin` stay in `app.workspace.auth`. Storage helpers stay in `app.workspace.storage_resolver` and `app.workspace.storage_validator`.

## Access

`get_current_principal` returns the first active account admin. When none exists it returns a principal with id `bbbbbbbb-0000-0000-0000-000000000001`, email `admin@compass.internal`, and `is_account_admin` true. `require_account_admin` returns that principal.

A `/w/{slug}` path, or a slug sent as `x-workspace-slug`, `x-workspace-id`, `workspace-id`, `workspace`, or `workspace_id`, goes through `resolve_workspace_context`. A refusal on an explicit slug is JSON `{"error": "<message>"}` with the status from `WorkspaceAuthError`. An inferred slug that fails is ignored and the request continues without a workspace context.

## Files

- `app/workspace/auth_routes.py`, `account_routes.py`, `workspace_routes.py` — HTTP facades
- `app/workspace/http/auth/application/` — legacy `/me` and workspace list
- `app/workspace/http/account/application/` — account, settings, workspaces, principals
- `app/workspace/http/workspace/application/` — workspace info, members, catalog visibility
- `app/workspace/middleware.py` — slug gate
- `app/workspace/storage_resolver.py`, `storage_validator.py` — storage
- `app/workspace/first_boot.py` — empty-database account
- `frontend/src/pages/workspace`, `account/AccountSettingsPage.tsx`, `CreateWorkspacePage.tsx` — screens

## Pages

- [Tenants](tenants.md)
- [Settings](settings.md)
- [Members](members.md)
- [Storage](storage.md)
- [Context](context.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
