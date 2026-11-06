# Agent runtime

Agent runtime is a sandbox-backed chat that is separate from the workspace agents. `main.py` mounts `app.agent_runtime.routes.router` at `/api/v1`, and the router prefix is `/agent-runtime`, so the paths are `/api/v1/agent-runtime/...`.

Sessions persist in the system table `agent_runtime_sessions` and in `~/.compassx/agent_runtime_sessions.json`. The id is `ars_` plus 12 hex characters. The service singleton is `agent_runtime_service`. Its logger is `app.agent_runtime.service`.

This module does not register an agent tool. There is no Tools page.

## What stays public

`app.agent_runtime.routes` still defines `router` and the handlers `list_sessions`, `create_session`, `get_session`, `delete_session`, and `send_message`. Each handler forwards to one application file. `app.agent_runtime` still exports `agent_runtime_service` and `router`.

## Access

List uses the `workspace_id` query when it is sent, otherwise `request.state.workspace.workspace_id`. Create uses the workspace on the request context and ignores a body workspace. Get, delete, and send load by session id only.

## Files

- `app/agent_runtime/routes.py` — HTTP facade
- `app/agent_runtime/http/sessions/application/` — one file per session action
- `app/agent_runtime/service.py` — sandbox binding and replies
- `app/agent_runtime/models.py` — request and row models
- `frontend/src/modules/agents/pages/AgentRuntimePage.tsx` — screen

## Pages

- [Sessions](sessions.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
