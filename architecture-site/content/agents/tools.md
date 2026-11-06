# Tools

The agent tool registry is `tool_registry` in `app.agents.services.agent.tools.registry`. The first use loads the core tools. A tool that fails to construct logs `Failed to instantiate tool %s: %s` and is skipped. `TOOL_MAP` and `TOOL_REGISTRY` are the older names for the same registry.

A person or an agent calls a built-in tool by its key during a chat turn. The orchestrator passes the key and arguments. The tool result comes back on the stream as a tool event.

## Registered keys

- `sql_warehouse`, `notebook_manager`, `dashboard_manager`, `mlflow`
- `python_code`, `visualization`, `rag_search`
- `catalog`, `catalog_editor`, `search_assets`
- `invoke_agent`, `list_available_skills`, `read_skill`
- `create_plan` — `Persist a new execution plan after landscape assessment. Returns plan_id.`
- `get_plan` — `Retrieve current plan state by plan_id.`
- `mark_step` — `Update a step status in an active plan.`
- `append_correction` — `Record a one-line correction note to a step without altering its status.`
- `get_next_step` — `Return the first pending step in an active plan, or null if complete.`
- `escalate_to_plan` — escalate the current task from a single action to a tracked plan
- `fetch_attachment` when the Nova tool imports

`catalog` is implemented in `app.catalog.tools`. `notebook_manager` and `dashboard_manager` call the Nova service modules. The keys are registered here.

## Catalog tool execution

`POST /api/v1/agent-tools/execute` runs a promoted catalog tool. The same handler is also mounted at `/agent-tools/execute` and hidden from the schema.

The body is `tool_id`, optional `version`, `connection_id`, `params`, `session_id`, and `agent_type`. `agent_type` defaults to `nova`.

The handler loads `UnifiedCatalogTool` by id, then by name. A miss is HTTP 404 `Tool '{id}' not found in catalog.` The caller must hold `EXECUTE` on `Securable.tool(catalog, schema, name)`. When `connection_id` is set, the caller must hold `USE_COMPUTE` on that connection. A missing connection is HTTP 404 `Connection not found`.

The response is `ok`, `result`, `truncated`, and, on failure, `error_type`, `message`, and `retryable`.
