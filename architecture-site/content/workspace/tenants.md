# Tenants

Account admin routes live on `app.workspace.account_routes`. The logger name is `app.workspace.account_routes`. The legacy sign-in list lives on `app.workspace.auth_routes`.

## Account

`GET /api/account` returns the first account row. A missing row is HTTP 404 `Account not found`. `PATCH /api/account` body `{ name }` renames that account and returns it.

`GET /api/auth/me` returns the principal from `get_current_principal`.

`GET /api/auth/workspaces` returns every active workspace when that principal is an account admin. Each item has `url` `/w/{slug}` and `role` `admin`. Anyone else gets active workspaces from `WorkspaceMembership`, with the membership role.

## Workspaces

`GET /api/account/workspaces` lists every workspace, including `storage_backend` and `url`.

`POST /api/account/workspaces` returns HTTP 201. A duplicate slug is HTTP 400 `Workspace slug already exists`. `storage_backend` defaults to `managed`. A managed workspace, or a body with no `storage_config`, stores backend `managed` and an empty config. Any other backend is validated and the sensitive fields are encrypted before they are stored. A validation failure is HTTP 400 with `Storage config validation failed: {error}`.

The creating admin is added as a legacy member with role `admin`. The handler also writes a system-database `UmWorkspaceRoleAssignment` with role `workspace_admin` and `is_default` true. A failure logs `Could not add system workspace role assignment: %s` or `Could not open system DB for workspace role assignment: %s` at warning.

It then creates or reuses an Iceberg catalog named `{normalized workspace name}_default`, binds it with privilege `READ_WRITE` and `is_default` true, and ensures schema `default`, volume `sample_data`, and notebook `getting_started`. The notebook comment is `Platform reference guide: Volumes (read/write), AI Agent Tools, and SQL querying`. A storage write failure logs `Could not write starter notebook content to storage: %s` and the notebook row is still added. A catalog or binding failure rolls back and returns HTTP 500 `Failed to create workspace due to catalog creation/binding error: {error}`.

After commit, the handler tries to create the default compute and SQL warehouse. A failure logs `Could not auto-ensure default compute/warehouse for workspace %s: %s` or `Could not open system DB for default compute/warehouse creation: %s`. It then clears the creator's entry-point cache. The response includes `url` `/w/{slug}`.

`GET /api/account/workspaces/{workspace_id}` reads one workspace. A miss is HTTP 404 `Workspace not found`. `PATCH` updates `name` and, when `storage_config` is sent, replaces the stored config with the encrypted copy.

`DELETE /api/account/workspaces/{workspace_id}` returns HTTP 202 `{ status: "accepted", workspace_id }` and sets status `deleting`. A background task deletes data-plane rows for that workspace, deletes workspace-visible catalog objects, and deletes the workspace row. Success logs `Workspace %s purged and deleted`. A purge failure logs `Error purging data plane for workspace %s` or `Error hard-deleting workspace %s` with the exception traceback.

## Principals

`GET /api/account/principals` lists principals in the admin's account.

`POST /api/account/principals` returns HTTP 201. `type` must be `user`, `group`, or `service_principal`, or the response is HTTP 400 `Invalid principal type`. A duplicate email in the account is HTTP 400 `Email already exists in this account`. A password is stored with `hash_password`, which keeps the password text as given.

`PATCH /api/account/principals/{principal_id}` updates `name`, `is_account_admin`, and `is_active` when those fields are sent. `DELETE` sets `is_active` false and returns HTTP 204. It does not remove the row. `POST .../reset-password` stores `new_password` and returns HTTP 204. A missing principal is HTTP 404 `Principal not found`.
