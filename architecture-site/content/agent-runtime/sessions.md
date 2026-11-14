# Sessions

## List and create

`GET /api/v1/agent-runtime/sessions` returns sessions for the workspace, including rows whose `workspace_id` is null, newest `updated_at` first. A database failure logs `[AgentRuntimeService] Failed to query sessions from DB, falling back to memory: %s` and returns the in-memory list with the same workspace rule.

`POST /api/v1/agent-runtime/sessions` returns HTTP 201. The title is the stripped body title or `Agent Session`. `agent_type` is lowercased. `agy` is stored as `antigravity`, `claude-code` and `claudecode` as `claude`, `cursor-agent` and `cursorcli` as `cursor`, and `compassx` and `compass` as `nova`. Any type the agent registry does not know, other than `bash`, is stored as `nova`. A `project_id` that does not exist is HTTP 400 `Project '{id}' does not exist.`

`sandbox_mode` `existing` with a `sandbox_id` uses that sandbox. A missing sandbox raises `Selected sandbox '{id}' does not exist.`, which the route returns as HTTP 400. Otherwise the service creates a sandbox named `{title} ({Agent})`, consumer `agent`, image `COMPASSX_SANDBOX_IMAGE` or `ghcr.io/compassx-platform/compassx-sandbox-host:latest`, port 8080, and working directory `/workspace`.

The new session's message list is empty. Any other create failure is HTTP 500 `Failed to create session: {error}`. A database save failure logs `[AgentRuntimeService] Failed to save session to DB: %s` and the session still returns. An Antigravity session tries to sync that sandbox's login and logs nothing when the sandbox is not running yet.

## Read, delete, and talk

`GET /sessions/{session_id}` returns the session and its messages. A miss is HTTP 404 `Session '{id}' not found.`

`DELETE /sessions/{session_id}` returns `{"deleted": true, "session_id": id}`. A miss is HTTP 404 `Session '{id}' not found.` A database delete failure logs `[AgentRuntimeService] Failed to delete session from DB: %s`.

`POST /sessions/{session_id}/messages` and `POST /sessions/{session_id}/start` body is `content` and optional `llm_model`. Both deliver that prompt. An empty message is HTTP 400 `Message is empty.` A missing session is HTTP 404 `Session '{id}' not found.` A sandbox that is not running is HTTP 409. Any other failure is HTTP 500 `Failed to process message: {error}`.

Nova types the prompt into the Nova process in the sandbox. Any other agent is started in tmux if needed, then the prompt is typed into that pane. The user message is appended to the transcript. A message save failure logs `[AgentRuntimeService] Failed to persist messages to DB: %s`.

`POST /sessions/{session_id}/notices/sync` copies new terminal activity into the transcript. A missing session is HTTP 404. A sandbox that is not running is HTTP 409. Any other failure is HTTP 500 `Failed to capture terminal errors: {error}`.

`GET /sessions/{session_id}/output` returns the live pane text. The same 404 and 409 rules apply. Any other failure is HTTP 500 `Failed to read agent output: {error}`.
