# Agent runtime

Agent runtime is a sandbox-backed chat that is separate from the workspace agents. `main.py` mounts `app.agent_runtime.routes.router` at `/api/v1`, and the router prefix is `/agent-runtime`, so the paths are `/api/v1/agent-runtime/...`.

Sessions persist in the system table `agent_runtime_sessions` and in `~/.compassx/agent_runtime_sessions.json`. The id is `ars_` plus 12 hex characters. The service singleton is `agent_runtime_service`. Its logger is `app.agent_runtime.service`.

The module owns one tool HTTP route, `POST /agent-runtime/sandbox/tools`. It is documented on the [Tools](tools.md) page. It does not register an agent tool record.

## What stays public

`app.agent_runtime.routes` still defines `router` and every handler name. Each handler forwards to one application file. `AgentRuntimeService` still defines the same methods. Each public method forwards to one file under `lifecycle/application/`. `app.agent_runtime` still exports `agent_runtime_service` and `router`. `ensure_nova_agent` and `ensure_nova_chat_session` stay importable from `app.agent_runtime.nova` and forward to `seeding/`.

## Access

List uses the `workspace_id` query when it is sent, otherwise `request.state.workspace.workspace_id`. Create uses the workspace on the request context and ignores a body workspace. Get, delete, and send load by session id only.

## Files

- `app/agent_runtime/routes.py` — HTTP facade
- `app/agent_runtime/http/` — one file per HTTP action
- `app/agent_runtime/service.py` — `AgentRuntimeService` facade. The logger stays `app.agent_runtime.service`
- `app/agent_runtime/lifecycle/application/` — one file per service action
- `app/agent_runtime/nova.py` — Nova agent and chat-session facade
- `app/agent_runtime/seeding/` — one file per Nova ensure action
- `app/agent_runtime/sandbox_tools.py` — host execution of a platform tool
- `app/agent_runtime/sandbox_controller.py` — Nova process inside the sandbox
- `app/agent_runtime/workspace.py` — shell commands for files and git
- `app/agent_runtime/browser_host.py` — host-owned browser
- `app/agent_runtime/models.py` — request and row models
- `frontend/src/modules/agents/pages/AgentRuntimePage.tsx` — screen

## Pages

- [Sessions](sessions.md)
- [Projects](projects.md)
- [Workspace files](workspace.md)
- [Browser](browser.md)
- [Tools](tools.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
