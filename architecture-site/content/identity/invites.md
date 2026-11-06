# Invites

Account admins create invites on `/api/um/account/invites`. Anyone with the token reads and accepts them on `/api/um/invites/{token}`. The accept route writes the user on the account database and, for a workspace invite, the membership on the system database.

## Create, list, revoke

`GET /api/um/account/invites` returns pending invites for the admin's account. The `invite_url` on a listed invite is `{FRONTEND_ORIGIN}/invite/[token]`. The raw token is not stored, so the list cannot rebuild it. `FRONTEND_ORIGIN` defaults to `http://localhost:5173`.

`POST /api/um/account/invites` returns HTTP 201. `target_scope` must be `account` or `workspace`, or the response is HTTP 400 `target_scope must be 'account' or 'workspace'`. A workspace invite without `target_workspace_id` is HTTP 400 `target_workspace_id required for workspace scope`. An email that already belongs to a user in the account is HTTP 400 `User already exists in this account`.

The token is `secrets.token_urlsafe(32)`. Only its hash is stored. Status is `pending`. Expiry is seven days. The audit action is `invite_created`. The handler logs `INVITE URL (stub email): %s` at info on the account-routes logger. The response `invite_url` is `{FRONTEND_ORIGIN}/invite/{raw token}`.

`DELETE /api/um/account/invites/{invite_id}` sets status `revoked` and audits `invite_revoked`. A missing invite is HTTP 404 `Invite not found`. The response is `{ status: "revoked", invite_id }`.

## Read and accept

`GET /api/um/invites/{token}` is public. The token is hashed and matched to `UmInvite.token_hash`. A missing invite is HTTP 404 `Invite not found`. Status `revoked` is HTTP 410 `This invite has been revoked. Contact your account admin.` Status `accepted` is HTTP 410 `This invite has already been accepted.` An `expires_at` in the past sets status `expired`, commits, and returns HTTP 410 `This invite has expired. Contact your account admin.`

`POST /api/um/invites/{token}/accept` body is `password`, `display_name`, and `confirm_password`. A mismatch is HTTP 400 `Passwords do not match`. A password shorter than 8 characters is HTTP 400 `Password must be at least 8 characters`.

An existing user with that email and account is updated: display name, password hash, and status `active`. Otherwise a new active local user is created. A proposed account role is assigned when the user does not already have one. A workspace-scoped invite with a workspace id and a proposed workspace role creates that membership when it is missing. The invite status becomes `accepted` and `accepted_at` is set. The audit action is `invite_accepted`.

The response is `access_token`, `refresh_token`, `user_id`, and `account_id`. The access token roles are the proposed account role, or an empty list when none was proposed.
