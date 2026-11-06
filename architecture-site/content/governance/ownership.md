# Ownership

One object has one owner row, `SecurableOwner`. There is no unowned state after creation. `guard.claim_ownership` calls `set_owner` with the caller as owner. A later call replaces the owner.

`GET /api/v1/governance/owner` takes `securable_type` and `name`. The caller must hold `BROWSE`. A missing owner returns JSON `null`. The response otherwise includes `owner_principal_id`, `owner_principal_type`, and `assigned_at`. The name in the response is the securable's full name.

`PUT /api/v1/governance/owner` transfers ownership. The body adds `owner_principal_id` and `owner_principal_type` (`user` or `group`). It requires `MANAGE`. The response is the new owner row.

`guard.relocate` moves grants and the owner row when an object's name or container changes. Grants are stored by catalog, schema, and asset. A rename that skips relocate leaves the old path granted and the new path empty.

## How a check is decided

`load_permission_set` decides in this order, and denies when none match:

1. Account admin, reason `account_admin`.
2. The principal plus their groups, or the agent service identity.
3. Workspace membership. A miss is `no_workspace_access`.
4. Ownership, reason `owner`.
5. `USE` on each ancestor catalog and schema. A break is `use_chain_broken`, and `detail` names the ancestor.
6. A grant on the object, reason `direct_grant`, or on an ancestor, reason `inherited_grant`.
7. Otherwise `no_grant`.

An agent is capped by its owner. A privilege the owner does not hold is `agent_ceiling_exceeded`.

`GET /api/v1/governance/effective` returns that picture. `principal_id` defaults to the caller. Inspecting another principal requires a workspace admin and uses the same 403 as the principal grant list. The response lists applicable privileges that are allowed, `is_owner`, and a `decisions` map. Each decision is the reason, and when `detail` is set, `{reason}: {detail}`.
