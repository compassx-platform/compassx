# Test cases

Run these in a workspace you can administer.

## Add an app

Open **Apps**. The heading should be **Apps**. Choose **Add app**. The dialog title should be **Add New App**. Enter a name such as `Capacity Overview`, leave the route empty, and continue to **Configure Git repository**. You can leave the repository empty. Submit.

You should see `App "Capacity Overview" created and registered in system DB.` The new app should appear in the list. Its route should be `/capacity-overview`. Opening it should show the app, not `App not found in this workspace.`

## Search and an empty name

On **Apps**, type `capacity` into `Search apps by name, repo, or branch...`. The list should keep `Capacity Overview` and hide apps whose name, repo, and branch do not match.

Choose **Add app** and submit the first step with an empty name. The dialog should stay open and the app should not be created.

## Deploy

Open `Capacity Overview` and deploy it on the default git ref.

You should get a deployment id that starts with `dep_`. A bad ref such as `main; rm` should be refused with `Invalid git ref.` and should not add a deployment. When the runner cannot build, you should see `Deployment failed:` and the app status should be `error`.

## Dev studio

From the app, open the build studio. Start the dev session.

The sandbox should become ready, and the file list should show the workspace. Write a file, then publish. The default commit message, when you do not type one, is `Update application via Omnigent Dev Studio`. Stop the session. The terminal should disconnect, and starting it again should resume the same app.

## Another workspace

Sign in to a different workspace and open the same app id.

The app should be missing from **Apps**. A direct request should say `App not found in this workspace.` or `Cannot access app in another workspace.`

## Omnigent server

As someone who can call the service API, request `GET /api/v1/services/omnigent/status`.

You should see `phase`, `message`, and `details`. Start it, then suspend it. Suspend should scale it down without deleting the volume. Resume should bring the same server back, and a later status call should show it running.
