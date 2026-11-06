# Grants

Grant rows are `ObjectGrant` on the system database. Changing them requires `MANAGE` on the object. The service message is `MANAGE on {name} is required to change its permissions.` The route returns that as HTTP 403.

## List

`GET /api/v1/governance/grants` takes `securable_type` and `name`. The caller must hold `MANAGE`. The list is the grants stored on that object, not grants inherited from a parent.

`GET /api/v1/governance/principals/{principal_id}/grants` lists every grant that principal holds in this workspace. A caller may read their own list. Reading someone else's requires an account admin or workspace role `workspace_admin`. Otherwise the response is HTTP 403 `Workspace admin is required to inspect another principal's access.`

## Grant

`POST /api/v1/governance/grants` returns HTTP 201. The body is `securable_type`, `name`, `principal_id`, `principal_type` (`user`, `group`, or `service`), `privileges`, and optional `expires_at`. Privileges and bundle names can be mixed. Each stored row is one privilege. Granting a privilege that is already stored does not add a second row. The response is only the rows created this time, so granting the same privilege again returns an empty list.

A grant to `principal_type` `service` is checked against the agent owner's permission set. If the owner does not hold the privilege, the response is HTTP 400 `Cannot grant {privilege} on {name} to this agent: its owner does not hold that privilege. An agent may never exceed the access of the principal responsible for it.`

Each new row writes an audit event `grant` with reason `granted to {type}:{id}`.

## Revoke

`POST /api/v1/governance/grants/revoke` takes `securable_type`, `name`, `principal_id`, and `privileges`. It returns `{ revoked: n }`, the number of rows deleted. Each named privilege writes an audit event `revoke` with reason `revoked from {principal_id}`, including when no row was deleted.
