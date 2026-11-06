# Members

`app.user_manager.routes.workspace_member_routes` serves `/api/um/workspaces`. The logger name is `app.user_manager.routes.workspace_member_routes`. Membership rows are `UmWorkspaceRoleAssignment` on the system database. The person, group, and service principal rows stay on the account database.

An unknown workspace role is HTTP 400 `Unknown workspace role: {role_id}`. A missing workspace, checked in the account database, is HTTP 404 `Workspace {id} not found`.

## List

`GET /{workspace_id}/members` is allowed for an account admin or anyone with a workspace role. Anyone else gets HTTP 403 `No access to this workspace`. Each row includes `assignment_id`, `principal_id`, `principal_type`, `role_id`, `is_default`, and `granted_at`. A user also gets `email` and `display_name`. A group gets `display_name` and `member_count`. A service principal gets `display_name` and `client_id`.

`GET /{workspace_id}/candidate-principals` requires a workspace admin. It returns account users who are not deactivated, groups, and service principals filtered with `UmServicePrincipal.active == True`, when those principals are not already assigned. User details are `User ({status})`. Group details are `Group · {n} members`. Service principal details are `Service Principal (OAuth)`.

## Assign, invite, create

`POST /{workspace_id}/members/assign` returns HTTP 201. The body is `principal_id`, `principal_type`, and `role_id` (default `analyst`). `principal_type` must be `user`, `group`, or `service_principal`. Anything else is HTTP 400 `Unsupported principal type: {type}`. A missing user is HTTP 404 `Account user not found`. A missing group is `Account group not found`. A missing service principal is `Account service principal not found`. An existing assignment is updated. The audit action is `workspace_principal_assigned`. The response is `{ status: "assigned", principal_id, role_id }`. A user assignment clears that user's entry-point cache.

`POST /{workspace_id}/members/invite` returns HTTP 201. The body is `email_or_user_id` and `role_id`. A value that is a UUID is looked up as a user id. Otherwise it is an email in the caller's account. When no user matches, the handler creates a pending workspace invite that expires in seven days, audits `invite_created`, and logs `WORKSPACE INVITE URL (stub): %s`. The response is `{ type: "invited", invite_id, invite_url }`. When a user matches, the membership is added or updated, the audit action is `member_added`, and the response is `{ type: "added", user_id }`.

`POST /{workspace_id}/members/create` returns HTTP 201. The body is `email`, `display_name`, `password`, and `role_id` (default `analyst`). An email that already exists in the account gets the workspace role and the response is `{ id, email, display_name, status: "added_existing" }`. A new user needs a password of at least 8 characters, or the response is HTTP 400 `Password must be at least 8 characters`. The new user is active, gets account role `account_viewer`, and gets the requested workspace role. The audit action is `user_created`. The response is `{ type: "created", user_id, email, role_id }`.

## Role, remove, default

`PATCH /{workspace_id}/members/{principal_id}/role` body `{ role_id }` updates the assignment and audits `role_changed`. A missing row is HTTP 404 `Membership not found`.

`DELETE /{workspace_id}/members/{principal_id}` deletes the assignment and audits `member_removed`. The response is `{ status: "removed", principal_id, workspace_id }`. A missing row is HTTP 404 `Membership not found`.

`POST /{workspace_id}/set-default` is the signed-in user's own default. The id may be a workspace UUID or a slug. The caller must already be able to reach that workspace, or the response is HTTP 403 `Not a member of this workspace`. Other direct defaults for that user are cleared. A missing direct row is created with the resolved role, or `workspace_admin` when the role is empty. The response is `{ workspace_id, is_default: true }` using the canonical workspace id. The caller's entry-point cache is cleared.
