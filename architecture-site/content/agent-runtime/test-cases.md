# Test cases

Run these in a workspace where sandboxes can be created.

## Create a session

Open **Agent Runtime**. Choose **Create Session**, leave the title as the default, and choose `bash`.

You should see a session whose id starts with `ars_` and whose agent type is `bash`. The message list is empty until you send a prompt. The sandbox working directory is `/workspace`.

## An existing sandbox

Create another session bound to a sandbox id that does not exist.

You should see `Selected sandbox '{id}' does not exist.` The session list should not gain a row.

## Talk to the sandbox

Open the session and send a sentence. Send an empty message as well.

The sentence should appear in the transcript as your message, and the agent pane in the sandbox should receive it. The empty message should be refused with `Message is empty.`

## List the agents and add a project

Open the agent list, then create a project named `Lab` and put a new session in it. Delete the project.

The list should include `nova`, `antigravity`, `pi`, `opencode`, `claude`, `codex`, and `cursor`. The project id should start with `arp_`. After delete, the session should still be there and should no longer name that project.

## Run a platform tool from the sandbox

From a Nova session inside a sandbox, call `POST /api/v1/agent-runtime/sandbox/tools` for `catalog` with the sandbox bearer token. Call the same path for `python_code`.

The catalog call should return that tool's result. `python_code` should be refused with HTTP 403 `Tool 'python_code' cannot run on the host.`

## Delete

Delete the session. You should see `Agent session deleted`. Opening the same id should say `Session '{id}' not found.`
