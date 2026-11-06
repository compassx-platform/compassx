# Test cases

The attachment routes are defined and are not mounted by `main.py`. These cases check the behavior of the route functions and the agent tool that is mounted.

## Fetch an attachment from chat

In a Nova or agent chat that has an uploaded file, ask the agent to read that attachment.

The tool call should use `fetch_attachment`. The reply should include the extracted text. An unknown file id should come back as a tool error rather than another workspace's file.

## Attachment routes, when the router is included

If a test app calls `register_agent_routers`, upload a file to `POST /api/v1/nova/sessions/{session_id}/attachments`.

You should get HTTP 201 and an `attachments` list with `file_id`, `filename`, and `status`. Listing the session should return that file. Deleting it should return HTTP 204. A later list should omit it because its status is `purged`. Reading that file id still returns the row, with status `purged`, until the row is gone. A missing session should say `Session not found`.

On the running `main.py` app, those `/api/v1/nova/...` paths are absent.
