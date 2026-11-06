# Account

`app.user_manager.routes.account_routes` serves `/api/um/account`. The logger name is `app.user_manager.routes.account_routes`. Every route requires an account admin.

## Users

`GET /users` lists users in the admin's account. Each item includes the effective account role and the count of direct workspace assignments.

`POST /users` returns HTTP 201. The body is `email`, `display_name`, `password`, and `account_role` (default `account_viewer`). A duplicate email is HTTP 400 `User with this email already exists`. A password shorter than 8 characters is HTTP 400 `Password must be at least 8 characters`. An unknown `account_role` is stored as `account_viewer`. The audit action is `user_created`.

`POST /users/{user_id}/suspend` sets status `suspended`, deletes that user's refresh tokens, and audits `user_suspended`. A missing user is HTTP 404 `User not found`. Suspending yourself is HTTP 400 `Cannot suspend yourself`.

`POST /users/{user_id}/reactivate` sets status `active` and audits `user_reactivated`. A deactivated user is HTTP 400 `Cannot reactivate a deactivated user`.

`POST /users/{user_id}/deactivate` sets status `deactivated`, deletes refresh tokens, and audits `user_deactivated`. Deactivating yourself is HTTP 400 `Cannot deactivate yourself`.

`PATCH /roles/{target_user_id}` body `{ role_id }` replaces or creates the account role assignment. An unknown role is HTTP 400 `Unknown account role: {role_id}`. The audit action is `role_granted`. The entry-point cache for that user is cleared.

## Groups

`GET /groups` lists groups in the account with `member_count`. `POST /groups` body `{ name }` returns HTTP 201. A duplicate name is HTTP 400 `Group name already exists`.

`GET /groups/{group_id}/members` lists members. A missing group is HTTP 404 `Group {id} not found`. `POST /groups/{group_id}/members` body `{ user_id }` returns HTTP 201. A missing user is HTTP 404 `User not found`. A duplicate is HTTP 400 `User already in group`. `DELETE /groups/{group_id}/members/{user_id}` returns `{ status: "removed" }`. A missing link is HTTP 404 `Member not found`. Adding or removing a member clears that user's entry-point cache.

`GET /groups/{group_id}/parent-groups` lists parent groups. `POST /groups/{group_id}/parent-groups` body `{ parent_group_id }` returns HTTP 201. The same id is HTTP 400 `A group cannot be a parent of itself`. A cycle is HTTP 400 `Circular group nesting detected`. An existing link is HTTP 400 `Group is already nested under this parent`. The audit action is `group_nested`. `DELETE .../parent-groups/{parent_group_id}` audits `group_unnested`. A missing link is HTTP 404 `Parent group relationship not found`.

`GET /groups/{group_id}/managers` lists managers. `POST /groups/{group_id}/managers` body `{ user_id }` returns HTTP 201. A duplicate is HTTP 400 `User is already a manager of this group`. The audit action is `group_manager_added`. `DELETE .../managers/{user_id}` audits `group_manager_removed`. A missing manager is HTTP 404 `Group manager not found`.

## Service principals

`GET /service-principals` lists principals in the account, including `secret_count`. `POST /service-principals` body `{ display_name }` returns HTTP 201. An empty name is HTTP 400 `display_name cannot be empty`. The audit action is `service_principal_created`.

`GET /service-principals/{sp_id}` reads one. `PATCH` accepts `display_name` and `is_active` and audits `service_principal_updated`. `DELETE` returns `{ status: "deleted", sp_id }` and audits `service_principal_deleted`. A missing principal is HTTP 404 `Service Principal not found`.

`GET /service-principals/{sp_id}/secrets` returns secret metadata. The secret value is not included. `POST .../secrets` body `{ expires_in_days }` defaults to 90. It returns HTTP 201 and `client_secret`, which starts with `cpx_sp_`. The stored prefix is the first 12 characters plus `...`. The audit action is `sp_secret_generated`. `expires_in_days` of 0 or null stores no expiry. `DELETE .../secrets/{secret_id}` audits `sp_secret_revoked`. A missing secret is HTTP 404 `Secret not found`.

## Workspaces and audit

`GET /workspaces` lists workspaces whose `account_id` is the admin's account, with a member count from workspace role assignments.

`GET /audit-log` filters by optional `actor_user_id`, `action`, and `workspace_id`. `limit` defaults to 100 and cannot exceed 500. `offset` defaults to 0. Rows are newest `created_at` first. The JSON field `metadata` is the column `metadata_`.
