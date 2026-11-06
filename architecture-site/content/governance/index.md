# Governance

Governance decides who can do what. Privileges, securable types, and bundles live in `app.governance.privileges`. A `Securable` is the address of one object. The resolver loads one permission set per request and is the only place an allow or deny is decided. The guard is what routes call. Grants and owners are rows on the system database.

The HTTP surface is `/api/v1/governance`. `main.py` includes `app.governance.routes.router`. This module does not register an agent tool. There is no Tools page.

Governance stays in this process. Other modules import `Guard`, `get_guard`, `Privilege`, and `Securable`. They do not copy the check.

## What stays public

`app.governance.routes` still defines `router` and the handler names `list_privileges`, `list_grants`, `list_principal_grants`, `create_grant`, `revoke_grant`, `get_owner`, `transfer_owner`, and `effective_permissions`. Each handler forwards to one application file. The logger stays `app.governance.routes`.

`grant`, `revoke`, `set_owner`, `transfer_ownership`, `relocate`, `ensure_agent_principal`, and `record_access_decision` stay in `app.governance.service`. `Guard`, `get_guard`, and `get_principal` stay in `app.governance.dependencies`. `load_permission_set` and `Decision` stay in `app.governance.resolver`.

## Access

`get_guard` needs a workspace context. Without one the response is HTTP 401 `Not authenticated for a workspace`. `current_workspace_id` answers HTTP 400 `No workspace context. Address this endpoint under /w/<workspace>.`

`guard.require` returns HTTP 404 `{type} not found` when the caller cannot browse the object. A missing workspace role is HTTP 403 `You do not have access to this workspace.` An agent past its owner's access is HTTP 403 `This agent may not access {name}: its owner does not have that access.` Any other miss is HTTP 403 `{privilege} on {name} is required.`

Lists use `guard.filter`. They drop hidden rows. They do not answer 403.

## Files

- `app/governance/routes.py` — HTTP facade
- `app/governance/http/grants/application/` — one file per governance route
- `app/governance/service.py` — grant, revoke, owner, audit
- `app/governance/dependencies.py` — principal and guard
- `app/governance/resolver.py` — permission set
- `app/governance/privileges.py` — vocabulary
- `app/governance/securable.py` — object address
- `app/governance/models.py` — `object_grants`, `securable_owners`, `agent_principals`, `access_audit_log`
- `frontend/src/modules/governance` — permissions panel

## Pages

- [Privileges](privileges.md)
- [Grants](grants.md)
- [Ownership](ownership.md)
- [Guard](guard.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
