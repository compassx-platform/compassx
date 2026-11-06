# Sign-in

`app.user_manager.routes.auth_routes` serves `/api/um/auth`. The logger name is `app.user_manager.routes.auth_routes`.

## Login

`POST /api/um/auth/login` takes `email` and `password`. The email is lowercased and trimmed. A missing user, a user with no password hash, or a wrong password is HTTP 401 `Invalid credentials`.

Status `suspended` is HTTP 403 `Account is suspended`. Status `deactivated` is HTTP 403 `Account is deactivated`. Status `invited` is changed to `active` and the login continues.

A successful login sets `last_login_at`, stores a hashed refresh token, and returns `access_token`, `refresh_token`, `user_id`, `email`, `display_name`, `account_id`, and `is_account_admin`. `is_account_admin` is true when the effective account role is `account_admin`. The refresh token expires after `REFRESH_TOKEN_TTL_DAYS`.

## Refresh and logout

`POST /api/um/auth/refresh` looks up the refresh token by its hash. The row must be unrevoked and unexpired. Otherwise the response is HTTP 401 `Invalid or expired refresh token`. A missing user, or a user who is `suspended` or `deactivated`, revokes that row and returns HTTP 403 `User not active`. A valid refresh returns a new `access_token` and does not rotate the refresh token.

`POST /api/um/auth/logout` takes the same refresh token body and returns HTTP 204. When the hash matches a row, that row's `revoked_at` is set. An unknown token still returns 204.

## Current user and memberships

`GET /api/um/auth/me` returns the signed-in user plus `account_role` from `get_effective_account_role`.

`GET /api/um/auth/workspaces` returns direct user memberships and memberships inherited through groups. A workspace id that is a UUID is matched on `Workspace.id`. Anything else is matched on `Workspace.slug`. The response uses the workspace id, name, and slug when the row exists. Duplicate workspace ids are skipped.

An account admin also receives every active workspace whose `account_id` is the user's account or null. When that query is empty, the admin receives every active workspace. Those extra rows use role `workspace_admin`. The first of them is `is_default` when the result list was empty before they were added.

## Service principal token

`POST /api/um/auth/sp-token` takes `application_id` and `client_secret`. The principal must be active. Each stored secret is checked with the password verifier, skipping a secret whose `expires_at` is in the past. A miss is HTTP 401 `Invalid application ID or secret`. The access token's roles are `["service_principal"]`. The response includes `access_token`, `sp_id`, `application_id`, `display_name`, and `account_id`.

## My groups

`GET /api/um/auth/my-groups` walks `um_group_members` and parent links in `um_group_nestings`. It returns each group in the caller's account, ordered by name, with `id`, `name`, `source`, and `member_count`.
