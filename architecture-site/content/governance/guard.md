# Guard

`get_guard` builds the `Guard` other modules depend on. It reads `request.state.workspace`. When that is missing it tries the workspace slug headers and query, then the default workspace for the token, and calls `resolve_workspace_context`. A failure is ignored. If there is still no context, the response is HTTP 401 `Not authenticated for a workspace`.

A principal id that starts with `id_app_` is type `service`, with the workspace role from the context or `workspace_developer`.

A request may send `x-active-role-id` or `x-active-group-id`. When that id is one of the user's groups, the principal's groups are that group and its ancestors only.

`guard.require(privilege, securable)` checks, writes an audit row for a denial and for an allow of an audited privilege, then raises the 403 or 404 from the overview. `guard.can` returns a boolean and does not raise. `guard.filter` keeps the items the caller can access.

`guard.require_workspace_admin(action)` allows an account admin or workspace role `workspace_admin`. Anyone else gets HTTP 403 `{action} requires workspace administrator.` Creating an agent uses the action text `Creating an agent`.

`guard.claim_ownership` sets the caller as owner. `guard.relocate` carries grants and ownership to a new path. `guard.as_agent(agent_id)` returns a guard whose permissions are the agent's grants intersected with the owner's.

`ensure_agent_principal` creates the service identity once. The owner stored there is the ceiling for later grants to that agent.
