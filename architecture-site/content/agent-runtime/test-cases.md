# Test cases

Run these in a workspace where sandboxes can be created.

## Create a session

Open **Agent Runtime**. Choose **Create Session**, leave the title as the default, and choose `bash`.

You should see `Agent session created (bash)`. The session id should start with `ars_`. The first assistant message should name `Shell Terminal` and the sandbox id. The sandbox working directory is `/workspace`.

## An existing sandbox

Create another session bound to a sandbox id that does not exist.

You should see `Selected sandbox '{id}' does not exist.` The session list should not gain a row.

## Talk to the sandbox

Open the session and send `$echo hello`.

The reply should start `**Executed in Sandbox` and include the command output. Send a normal sentence. The reply should start `**[Shell Terminal Response]**` and include the sandbox id.

## Delete

Delete the session. You should see `Agent session deleted`. Opening the same id should say `Session '{id}' not found.`
