# Setup

`app.user_manager.routes.setup_routes` serves `/api/um/setup`. The logger name is `app.user_manager.routes.setup_routes`. These routes are public. They do not take an access token.

## Status

`GET /api/um/setup/status` returns `{ needs_setup }`. When the account table has no row, `needs_setup` is true. When the account row has no `setup_completed` value, `needs_setup` is true only when the user table is empty. Otherwise `needs_setup` is the opposite of `setup_completed`.

## Complete

`POST /api/um/setup/complete` returns HTTP 201. The body is `account_name`, `admin_email`, `admin_password`, `admin_display_name`, and an optional `workspace_name`.

If any user already has an `account_id`, the response is HTTP 403 `Setup already completed`.

The handler seeds account roles, workspace roles, landing rules, permissions, and object roles. It reuses the first account row, or creates one whose slug is the account name in lowercase with spaces replaced by hyphens. It creates an active local admin, assigns `account_admin`, and creates a workspace. The workspace name is the trimmed `workspace_name`, or `default`. The slug is that name in lowercase with spaces replaced by hyphens. Storage backend is `managed` and `storage_config` is `{}`. The admin's workspace role is `workspace_admin` and `is_default` is true. A legacy principal row is added for the admin when one is missing.

A failure to ensure the default storage bucket logs `Could not auto-ensure default storage bucket: %s` at warning and setup continues. A failure to create the workspace logs `Could not create initial workspace: %s` at warning and setup still returns tokens.

When the workspace row was created, setup also tries to bind a default catalog named `{normalized workspace}_default`, type `iceberg`, schema `default`, privilege `READ_WRITE`, `is_default` true. A failure logs `Could not auto-create/bind default catalog in setup_complete: %s`. It then calls `ensure_workspace_default_resources` with the request's `runtime_manager` when the request is present. A failure logs `Could not auto-ensure default compute/warehouse in setup_complete: %s`.

Success logs `Setup complete: account=%s, admin=%s, workspace=%s` at info. The response is `access_token`, `refresh_token`, `user_id`, and `account_id`. The access token roles are `["account_admin"]`.
