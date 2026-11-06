# MCP servers

`/api/v1/ai-gateway/mcp` registers Model Context Protocol servers and serves the MCP wire protocol. Saved servers live in the account table `mcp_servers`. Built-in servers are not rows. They are the four objects in `BUILTIN_MCP_SERVERS`.

Server types are `native`, `remote_sse`, and `subprocess`.

## List and identity

`GET /mcp/servers` returns the built-ins first, then saved servers whose name is not already present. A built-in row uses catalog `system`, schema `ai`, full name `system.ai.{name}`, type `native`, and endpoint `{base}/api/v1/ai-gateway/mcp/servers/{name}/sse`. The base URL is `x-forwarded-proto` or the request scheme, plus `x-forwarded-host` or `host`, and `https://135.13.180.167.nip.io` when no host header is present. The built-in id is `abs(hash(name)) % 100000 + 1`.

A saved server's full name is `{catalog or default}.{schema or default}.{name}`. A native saved server with no endpoint URL gets `{base}/api/v1/ai-gateway/mcp/servers/{name}/sse`.

`_resolve_mcp_server` accepts a built-in name, these aliases, a `catalog.schema.name`, a `schema.name`, a numeric id, or a plain name:

- `native_sql` and `system.ai.native_sql` and `system.ai.compassx_sql_warehouse` resolve to `compassx_sql_warehouse`
- `native_catalog` and `system.ai.native_catalog` and `system.ai.compassx_catalog_search` resolve to `compassx_catalog_search`

## Register, update, delete

`POST /mcp/servers` returns HTTP 201. A duplicate name in the workspace scope is HTTP 400 `MCP server '{name}' already registered.` Auth headers and env vars are encrypted JSON. `created_by` is `request.state.user_email` or `system`. For `remote_sse` or `subprocess` with an endpoint or a command, the handler syncs tools immediately. A sync failure logs `Initial tools discovery for MCP server '%s' completed with warning: %s` and still returns the server.

`GET /mcp/servers/{server_id}` returns HTTP 404 `MCP server not found` when the identifier is not a saved row. A built-in match has no database row, so this route returns that 404 for a built-in name.

`PUT /mcp/servers/{server_id}` updates the fields present on the body, then syncs remote or subprocess tools. A sync failure logs `Tools sync for updated MCP server '%s' warning: %s`.

`DELETE /mcp/servers/{server_id}` returns HTTP 204. A missing saved row is HTTP 404 `MCP server not found`.

## Wire protocol

`GET /mcp/sse` opens the unified SSE stream. `GET /mcp/servers/{server_name}/sse` and `GET /mcp/servers/{server_name}/mcp` open the stream for one server.

`POST /mcp/sse` and `POST /mcp/mcp` accept a JSON-RPC body, or a list of bodies, for every server. `POST /mcp/servers/{server_name}`, `POST /mcp/servers/{server_name}/sse`, and `POST /mcp/servers/{server_name}/mcp` do the same for one server. An unreadable body is HTTP 400 `Invalid JSON body`. `session_id` selects an existing MCP session.

`POST /mcp/messages` is the same JSON-RPC handler. When the session is active and the response contains `result`, the response is also placed on the session queue.

`GET /mcp/config/omnigent` returns `build_mcp_configs_from_gateway` for the workspace. That payload is the shape written for Claude Code, OpenCode, Antigravity, and Codex.

## Tool list and call

`GET` or `POST /mcp/servers/{server_id}/tools`, and `POST /mcp/servers/{server_id}/ping`, return the live tool list. A built-in success message is `Successfully retrieved tools from native MCP server '{name}'`. A saved server success message is `Successfully retrieved tools from MCP server '{name}' via {TYPE}`. A missing server is HTTP 404 `MCP server '{id}' not found`. A sync exception logs `Error retrieving tools for MCP server %s: %s` and returns `success: false` with `Failed to retrieve tools: {error}` and JSON-RPC error code `-32603`. `latency_ms` is at least 1. `called_endpoint` is `/api/v1/ai-gateway/mcp/servers/{full name}/tools`.

`GET /mcp/tools` returns every tool `MCPManager.list_all_tools_for_workspace` collects.

`POST /mcp/tools/call` runs `MCPExecutionProxy.execute_tool` with the body tool name, arguments, caller id, and server id. The user id on that call is null. A failed audit write logs `Could not write tool execution audit log: %s` from `app.ai_gateway.mcp.proxy`.
