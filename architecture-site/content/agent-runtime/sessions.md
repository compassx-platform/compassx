# Sessions

## List and create

`GET /api/v1/agent-runtime/sessions` returns sessions for the workspace, including rows whose `workspace_id` is null, newest `updated_at` first. A database failure logs `[AgentRuntimeService] Failed to query sessions from DB, falling back to memory: %s` and returns the in-memory list with the same workspace rule.

`POST /api/v1/agent-runtime/sessions` returns HTTP 201. The title is the stripped body title or `Agent Session`. `agent_type` is `antigravity`, `pi`, `opencode`, or `bash`. Any other value is stored as `antigravity`.

`sandbox_mode` `existing` with a `sandbox_id` uses that sandbox. A missing sandbox raises `Selected sandbox '{id}' does not exist.`, which the route returns as HTTP 400. Otherwise the service creates a sandbox named `{title} ({Agent})`, consumer `agent`, image `COMPASSX_SANDBOX_IMAGE` or `ghcr.io/compassx-platform/compassx-sandbox-host:latest`, port 8080, and working directory `/workspace`.

The first message is an assistant greeting that names the agent and the sandbox id. Display names are `Google Antigravity (agy)`, `Pi Coding Agent`, `OpenCode AI`, and `Shell Terminal`. Any other create failure is HTTP 500 `Failed to create session: {error}`. A database save failure logs `[AgentRuntimeService] Failed to save session to DB: %s` and the session still returns.

## Read, delete, and talk

`GET /sessions/{session_id}` returns the session and its messages. A miss is HTTP 404 `Session '{id}' not found.`

`DELETE /sessions/{session_id}` returns `{"deleted": true, "session_id": id}`. A miss is HTTP 404 `Session '{id}' not found.` A database delete failure logs `[AgentRuntimeService] Failed to delete session from DB: %s`.

`POST /sessions/{session_id}/messages` body is `content`. A missing session is HTTP 404 with `Session '{id}' not found.` Any other failure is HTTP 500 `Failed to process message: {error}`.

A message that starts with `$` runs the rest as a sandbox command with a 30 second timeout. The reply starts `**Executed in Sandbox (`{id}`):**`. Any other message returns a reply that starts `**[{display name} Response]**` and includes the sandbox id and status. A message save failure logs `[AgentRuntimeService] Failed to persist messages to DB: %s`.
