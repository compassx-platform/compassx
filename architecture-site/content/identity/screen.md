# Screen

The client is `frontend/src/lib/userManagerApi.ts`. Routes are declared in `frontend/src/App.tsx`.

`/login` renders `LoginPage`. The heading is CompassX. The subtitle is `Sign in to your account`. A wrong password shows `Invalid email or password. Please try again.` After a successful login the page asks `GET /api/um/entry-point` and navigates to `route`.

`/setup` renders `SetupWizardPage`. The heading is `CompassX Initial Setup`. The subtitle is `Set up your organization account & admin user`. Submitting calls `POST /api/um/setup/complete`.

`/invite/:token` renders `InviteAcceptancePage`. The heading is `Accept Invitation`. An unusable token shows `Invalid or Expired Invite`.

`/workspace-picker` renders `WorkspacePickerPage`. The heading is `Select a Workspace`. The subtitle is `Choose where you want to work today.` Choosing one calls `POST /api/um/workspaces/{id}/set-default` and then loads the entry point again.

`/no-workspace-access` shows `No Workspace Found` for an account admin and `No Workspace Access` for anyone else.

`/account` renders `AccountConsolePage`. The heading is `Account Console`. The tabs are Identity Hub, Users, Groups, Service Principals, Invites, Workspaces, Audit Log, and Settings. Creating a user with a short password shows `Password must be at least 8 characters` before the request is sent. A failed create shows the response detail, or `Failed to create user`.

`/account/workspaces/:workspaceId/members` renders `WorkspaceMembersPage`. The title is `Workspace Permissions & Identity`. Filters are All Identities, Users, Groups, and Service Principals. The admin button is `Assign to Workspace`. A successful assign shows `✓ Assigned {name} ({type}) to workspace`. A created user shows `✓ Created user {email} and granted workspace access`. An invite shows `✓ Invitation link generated for {email}` and the invite URL. An existing user added by email shows `✓ Added {email} directly to workspace`.
