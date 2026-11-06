# Test cases

Run these from **Compute**, on the **Sandboxes** tab. The heading on that page is **Compute**.

## Provision a sandbox

Choose **Provision Sandbox**. The dialog title should be **Provision Compute Sandbox**. Leave the name empty and submit.

You should see `Sandbox name is required.` and no new row.

Enter `app-build-sandbox-1`, leave the image on CompassX Sandbox Host, ports `8080`, and an init command `python -c "print('ready')"`. Choose **Provision Sandbox**.

The dialog should close and the row should appear. Its status should reach ready. Opening it should show the name `app-build-sandbox-1` and a **Sandboxes** button back to the list.

## Run the same sandbox again

Provision again with the same consumer key, or call ensure for the same `sandbox_id`.

You should get the same id back, with progress message `Sandbox is active and ready`. A second container should not be created for that key.

## Suspend, resume, and use the terminal

On the open sandbox, choose **Suspend**. You should see `Suspending sandbox compute...` and the status should become suspended.

Choose **Resume**. You should see `Resuming sandbox compute...` and the status should become running.

Open the terminal. For a shell session you should see `Connected to Sandbox Terminal` and the sandbox name. Type a command that prints `hello`. You should see `hello` in the terminal. A sandbox id that does not exist should close the socket and say `Sandbox '{id}' not found`.

## Logs and a missing command target

Open the logs for `app-build-sandbox-1`. You should see the init output, including `ready` when that command ran.

Request logs for an id that was never created. The call should succeed and the log text should be `[Sandbox '{id}' not found]`.

## Terminate

Choose **Terminate Sandbox**. The confirm title should be **Terminate Sandbox**, and the message should say the running processes and ephemeral state will be permanently removed. Confirm **Terminate**.

You should see `Sandbox terminated successfully`, and the row should leave the list. Terminating an id that is already gone should still report terminated.
