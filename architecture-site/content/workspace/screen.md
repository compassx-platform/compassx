# Screen

`/workspace/create` renders `CreateWorkspacePage`. The heading is `Create a Workspace`. Submitting calls `POST /api/account/workspaces`.

`/w/{slug}/settings` and `/w/{slug}/workspace-settings` render `WorkspaceSettingsPage`. The heading is `Workspace Settings`. The page reads and saves `GET` and `PATCH /api/w/{slug}/api/workspace/settings`.

`/account/settings` and `/account-settings` render `AccountSettingsPage`. The heading is `Account Settings`. The same page is also mounted inside a workspace at `account-settings` and `account/settings`. It reads and saves `/api/account/settings`, and it calls the node-pool and compute provision, deprovision, switchover, and status routes.

The workspace picker and the no-workspace page belong to Identity. Their `+ Create Workspace` button navigates to workspace create.
