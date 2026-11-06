# Test cases

Run these as a workspace admin, then repeat the read-only cases as a member who is not an admin.

## Create an agent

Open **Agents**. The heading should be **Agents**. Create an agent named `Capacity Analyst` with a prompt and one tool.

You should land on that agent. A member who is not a workspace admin should be refused with `Creating an agent`. Opening another workspace's agent id should say `Agent not found`.

## Chat and a tool

Open `Capacity Analyst` and send a question that needs the catalog or SQL tool.

You should see the reply on the transcript, and a tool card for the tool that ran. **Active Streams** should show the turn while it is running. **LLM Call Logs** should gain a row. Cancelling the stream should stop new events.

## Skills and a budget

Open **Skills Library**. Save a skill with an empty name. You should see `Skill name is required`. Save one named `Warehouse notes`. You should see `Skill created successfully`. Attach it to `Capacity Analyst`. Saving the same name again should say `Skill with this name already exists`.

Open **Budgets** and add an active monthly budget for that agent. Saving a second active monthly budget for the same agent should say `An active monthly budget already exists`.

## Connections

Open **Connections**. The heading should be **Connections**. Add a database connection and test it. Success should toast `Connection` and `OK`, or the test message from the database page. A bad password should toast `Test failed` or `Connection test failed`.

`POST /api/v1/agent-tools/execute` with an unknown `tool_id` should say `Tool '{id}' not found in catalog.`

## Documents

In the chat, upload a file. It should appear on the session. Upload with no file selected should be refused with `No files uploaded` when the request is empty. Delete the document. It should disappear, and a second delete should say `Document not found`.
