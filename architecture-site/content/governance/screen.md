# Screen

Governance has no page of its own. `frontend/src/modules/governance` is the permissions panel other screens embed. The client is `governanceApi.ts`. Calls go to `/governance`, and the shared API client sends the workspace on `X-Workspace-Slug`.

`PermissionsPanel` shows the owner, the direct grants, and effective access. The grants title is `Grants on this {type}`. The help text says direct grants only, and points at Effective access for inheritance. An empty list says `No direct grants on this {type}.` The button is `Grant access`. While grants load, the panel says `Loading grants…`.

`GrantDialog` heading is `Grant access`. The field label is `Grant to`. A principal who already has a grant shows `Has access`. The submit button says `Granting…` while the request is in flight, then `Grant`. Success toast is `Granted {n} privilege(s) to {name}.` A repeat grant that creates no rows still uses that sentence with zero.

`OwnerBadge` label is `Owner`. The transfer note says `Ownership carries full control.` Success toast is `{name} is now owned by {label}.`

`EffectivePermissions` shows Allowed or Denied. The reason tokens from the resolver are shown as:

| Token | Text |
| --- | --- |
| `account_admin` | Granted by account administrator role |
| `workspace_admin` | Granted by workspace administrator role. Analyst, business viewer, workspace developer, and app executor roles do not skip grants |
| `owner` | Granted by ownership |
| `direct_grant` | Granted directly on this object |
| `inherited_grant` | Inherited from a parent |
| `no_workspace_access` | No access to this workspace |
| `use_chain_broken` | Blocked — missing USE on a parent container |
| `agent_ceiling_exceeded` | Blocked — the agent's owner does not have this access |
| `no_grant` | No grant |

A reason with a detail is `{text} — {detail}`.
