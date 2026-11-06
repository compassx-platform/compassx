# Members

These are the legacy memberships on `WorkspaceMembership`. User-manager members, invites, and the workspace picker stay in Identity.

`GET /api/w/{slug}/api/workspace/members` lists memberships for the workspace on the request context. Each item includes the principal row.

`POST /api/w/{slug}/api/workspace/members` returns HTTP 201. It requires a workspace admin. `role` must be `admin`, `member`, or `viewer`, or the response is HTTP 400 `Invalid role`. A duplicate principal is HTTP 400 `Principal already a member`. A missing principal is HTTP 404 `Principal not found`. `granted_by` is the caller on the workspace context.

`PATCH /api/w/{slug}/api/workspace/members/{member_id}` changes the role under the same admin check and role list. A membership outside this workspace, or a missing row, is HTTP 404 `Membership not found`.

`DELETE /api/w/{slug}/api/workspace/members/{member_id}` deletes that row and returns HTTP 204.

A request with no workspace context is HTTP 400 `Missing workspace context`.
