# Test cases

These are product checks inside a workspace, signed in as someone who can open a table.

## See why access was denied

Open a table you can browse but cannot modify. Open its permissions panel. Effective access should show `SELECT` as Allowed and `MODIFY` as Denied, with the reason `No grant` or `Inherited from a parent` when a parent grant is what allows the read. You should see the owner name. You should not see the grant editor unless you hold `MANAGE`.

## Grant and revoke

As the owner, open the same panel. You should see `Grant access` and `Grants on this table`. Grant `SELECT` to another user. The toast should say `Granted 1 privilege to {name}.` Grant `SELECT` to that user again. The toast should say `Granted 0 privileges to {name}`, and the grant list should still show one `SELECT` row. Revoke it. The list should drop that privilege. The response of the revoke call should be `{ revoked: 1 }`.

Grant `SELECT` on a job. You should see that `SELECT` is not applicable to `job`.

## Owner

Transfer the table to another user. The toast should say the table is now owned by that person. Sign in as the new owner. You should be able to grant `SELECT` without being a workspace admin. Sign in as a user who can browse the table and cannot manage it. The owner should still be visible.

## Someone else's access

As a user who is not a workspace admin, request `GET /api/v1/governance/principals/{other user}/grants`. You should see `Workspace admin is required to inspect another principal's access.` Request your own principal id. You should get your grants. As a workspace admin, request the other user's effective permissions on the table. You should see their privilege list and a decision for each applicable privilege.

## Hidden object

As a user with no `BROWSE` on a table, request `GET /api/v1/governance/owner` for it. You should get HTTP 404 `{type} not found`, not a message that names the missing privilege.
