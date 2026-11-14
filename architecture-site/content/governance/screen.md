# Screen

Governance has no page of its own. `frontend/src/modules/governance` is the permissions panel other screens embed. The client is `governanceApi.ts`. Calls go to `/governance`, and the shared API client sends the workspace on `X-Workspace-Slug`.

`PermissionsPanel` is one header row and one grants table. The header shows the object name and the owner on a single line. The change-owner action is `Change owner`. The table columns are Principal, Privilege, and Granted. A grant on this object reads `This object`. A grant whose securable is a parent reads `Inherited from {name}` and the row is quieter. An empty list is one sentence: `No grants on this {type}.` The primary button is `Grant`. While grants load, the panel says `Loading grants…`. Effective access is a closed disclosure labeled `Effective access`.

`GrantDialog` heading is `Grant`. The object name sits under that heading. The field label is `Grant to`. Privilege and bundle share one picker; choosing a bundle fills the privilege set, and each chosen privilege is a removable chip. A principal who already has a grant shows `Has access`. The submit button says `Granting…` while the request is in flight, then `Grant`. Success toast is `Granted {n} privilege(s) to {name}.` When the grant creates no new rows, the toast is `{name} already had those privileges.`

`OwnerBadge` label is `Owner`. The action is `Change owner`. The transfer note says `Ownership carries full control.` Success toast is `{name} is now owned by {label}.`

`EffectivePermissions` sits inside the disclosure. It shows Allowed or Denied, with the reason beside that word. The reason tokens from the resolver are shown as:

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
