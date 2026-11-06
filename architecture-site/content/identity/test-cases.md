# Test cases

These are product checks. Sign in as the account admin created by setup unless a case says otherwise.

## First setup

Open `/setup` on an instance with no users. Submit an account name, admin email, password, display name, and workspace name. You should land signed in, and `GET /api/um/setup/status` should report `needs_setup` false. Submit setup a second time. You should see `Setup already completed`.

## Sign in

Open `/login`. Enter a wrong password. You should see `Invalid email or password. Please try again.` Enter the admin password. You should leave the login page on the entry-point route. Call `GET /api/um/auth/me`. You should see the admin email and account role `account_admin`. Call logout with the refresh token, then call refresh with that same token. Refresh should say `Invalid or expired refresh token`.

## Suspended user

On Account Console, Users, create a user with a password of at least 8 characters. Sign in as that user, then sign back in as admin and suspend the user. The next login for that user should say `Account is suspended`. Reactivate the user. The user should be able to sign in again.

## Invite

On Account Console, Invites, send a workspace invite. The server log should contain `INVITE URL (stub email):`. Open that URL. The page heading should be `Accept Invitation`. Submit two different passwords. You should see `Passwords do not match`. Submit a matching password of at least 8 characters and a display name. You should receive tokens and the invite should no longer be pending. Open the same URL again. You should see that the invite has already been accepted.

## Groups and service principals

On Account Console, Groups, create a group and add the user from the suspend case. Nesting the group under itself should say `A group cannot be a parent of itself`. On Service Principals, create one named `billing-job`. Generate a secret. You should see a `client_secret` that starts with `cpx_sp_`, and a later list of secrets should show the prefix only. `POST /api/um/auth/sp-token` with that application id and secret should return an access token. The same call with a wrong secret should say `Invalid application ID or secret`.

## Workspace members

Open `/account/workspaces/{workspace id}/members`. The title should be `Workspace Permissions & Identity`. Assign an existing user as `analyst`. You should see `Assigned` in the confirmation. Invite an email that is not a user yet. You should see `Invitation link generated` and a URL. Set that workspace as the default from the workspace picker. The next `GET /api/um/entry-point` should return that workspace with `section` `app` and a route under `/w/{slug}`.

## Several workspaces and no default

Give a non-admin user two workspace memberships and clear `is_default` on both. Sign in as that user. You should land on `/workspace-picker` with the heading `Select a Workspace`. Remove every membership from a non-admin user and sign in. You should see `No Workspace Access`.
