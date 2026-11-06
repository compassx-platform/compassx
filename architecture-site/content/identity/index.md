# Identity

Identity is the user manager. It stores the account's people, groups, invites, and service principals on the account database, and it stores workspace membership on the system database. Sign-in, first-time setup, invite acceptance, and the post-login landing all live here.

The HTTP surface is `/api/um`. `main.py` includes six routers from `app.user_manager.routes`: setup, auth, account, workspace members, invites, and the entry point. This module does not register an agent tool. There is no Tools page.

Workspace tenants, storage configuration, and the older `/api/auth` and `/api/account` routes stay in `app.workspace`. They are the Workspace module. Identity does not move out of this process, and it keeps sharing the account database with Workspace.

## What stays public

Each route module still defines `router` and the same handler names. `setup_complete` and `SetupCompleteIn` stay importable from `app.user_manager.routes.setup_routes`. `set_default_workspace` stays importable from `app.user_manager.routes.workspace_member_routes`.

Each handler forwards to one application file. Loggers stay on the original route module names, such as `app.user_manager.routes.auth_routes`.

`get_current_um_user`, `require_um_account_admin`, and `require_workspace_admin` stay in `app.user_manager.dependencies`. Password hashing and token helpers stay in `app.user_manager.auth_utils`. `resolve_entry_point` stays in `app.user_manager.entry_point`.

## Access

A missing or expired access token is HTTP 401 `Not authenticated`, `Token expired`, or `Invalid token: {error}`. A token with no user id is `Invalid token payload`. An unknown user is `User not found`. A user whose status is not `active` is HTTP 403 `Account is {status}`, except an `invited` user, who is allowed through.

Account admin routes use `require_um_account_admin`. Anyone else gets HTTP 403 `Account admin required`. Workspace member changes use `require_workspace_admin`, which answers HTTP 403 `Workspace admin required`. An account admin passes that check without a workspace role.

## Files

- `app/user_manager/routes/` — HTTP facades
- `app/user_manager/http/setup/application/` — first-time setup
- `app/user_manager/http/auth/application/` — sign-in, refresh, logout, me, memberships, service-principal token, groups
- `app/user_manager/http/account/application/` — users, roles, invites, groups, service principals, audit
- `app/user_manager/http/invites/application/` — public invite read and accept
- `app/user_manager/http/members/application/` — workspace membership
- `app/user_manager/http/entry_point/application/` — post-login landing
- `app/user_manager/models/` — account and system tables
- `frontend/src/lib/userManagerApi.ts` — screen client
- `frontend/src/pages/auth`, `setup`, `invite`, `account`, `workspace`, `workspace-picker`, `no-workspace` — screens

## Pages

- [Sign-in](sign-in.md)
- [Setup](setup.md)
- [Account](account.md)
- [Invites](invites.md)
- [Members](members.md)
- [Entry point](entry.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
