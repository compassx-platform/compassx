# Agents

An agent is a workspace definition stored on the account `Agent` table. It has a prompt, a model, tools, and skills, and it runs chat under its own grants. The HTTP surface is mounted from `app.agents.routes` in `main.py`.

Creating an agent requires a workspace admin. The guard message is `Creating an agent`. Reading an agent requires `BROWSE`. Changing it requires `EDIT`. Deleting it requires `MANAGE`. A missing agent in this workspace is HTTP 404 `Agent not found`. A request with no workspace context is HTTP 400 `No workspace context. Address this endpoint under /w/<workspace>.`

Chat, documents, plans, and proposed changes belong to the agent. They have no grants of their own. A missing session is HTTP 404 `Session not found`.

This module registers the agent tools. They are documented on the [Tools](tools.md) page.

## What stays public

`app.agents.routes` still exports the route modules `main.py` includes. Each module still defines `router` and the same handler names. `app.routes.agent_routes`, `chat_routes`, `llm_connection_routes`, `db_connection_routes`, `git_connection_routes`, and `agent_context_routes` still star-import those modules.

`app.agents.routes._authz` still provides `workspace_id_of`, `authorized_agent`, `visible_agents`, `authorized_session`, `authorized_connection`, and `visible_connections`.

Each handler forwards to one application file. Loggers stay on the original route module names, such as `app.agents.routes.agent_routes`.

`register_agent_routers` still lists the same routers, including Nova attachments. `main.py` does not call it. `main.py` includes the agent routers itself and does not include the Nova attachment router.

## Files

- `app/agents/routes/` — HTTP facades
- `app/agents/http/records/application/` — agent create, read, update, delete, clone
- `app/agents/http/context/application/` — context entries
- `app/agents/http/chat/application/` — sessions and streaming
- `app/agents/http/skills/application/` — skill library
- `app/agents/http/llm_connections/application/`, `db_connections/`, `git_connections/`, `external_connections/` — connections
- `app/agents/http/streams/application/`, `llm_calls/`, `budgets/`
- `app/agents/http/documents/application/`, `artifacts/`
- `app/agents/http/tool_execution/application/` — catalog tool execution
- `app/agents/services/agent/` — orchestrator, tool registry, plans
- `frontend/src/modules/agents` — screen

## Pages

- [Records](records.md)
- [Chat](chat.md)
- [Tools](tools.md)
- [Connections](connections.md)
- [Skills, budgets, and logs](skills.md)
- [Documents and changes](documents.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
