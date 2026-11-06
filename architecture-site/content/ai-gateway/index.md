# AI Gateway

The AI Gateway is the workspace front door for model calls and MCP tools. Account tables `ai_providers`, `ai_model_endpoints`, and `mcp_servers` hold the configuration. System tables `ai_gateway_inference_logs` and `ai_gateway_tool_logs` hold the audit rows.

`main.py` mounts four routers:

- `/api/v1/ai-gateway/providers`
- `/api/v1/ai-gateway/mcp`
- `/api/v1/ai-gateway/v1`
- `/api/v1/ai-gateway/logs`

`app.ai_gateway.routes.endpoint_routes` defines `/api/v1/ai-gateway/endpoints`. That router is not included by `main.py`, so those paths are not served. Endpoints that the product actually uses are created by `GET /api/v1/ai-gateway/v1/models` and by `GatewayService.resolve_endpoint`.

The module exposes MCP tools. They are documented on the [Tools](tools.md) page.

## What stays public

`app.ai_gateway.routes` still exports `provider_router`, `mcp_router`, `proxy_router`, and `log_router`. Each route module still defines `router` and the same handler names. Helpers such as `_get_workspace_id`, `_to_provider_response`, `_resolve_caller_and_workspace`, `_resolve_mcp_server`, and `get_system_db` stay on those modules.

Each handler forwards to one application file. Loggers stay `app.ai_gateway.routes.provider_routes`, `app.ai_gateway.routes.endpoint_routes`, `app.ai_gateway.routes.proxy_routes`, `app.ai_gateway.routes.mcp_routes`, `app.ai_gateway.routes.log_routes`, and `app.ai_gateway.services.gateway_service`.

`GatewayService`, the provider adapters, the MCP client, and the SQLAlchemy models stay where callers already import them.

## Access

A workspace id is taken from `request.state.workspace.workspace_id` when that value is a UUID. Otherwise it is taken from the `X-Workspace-Id` header or the `workspace_id` query, and only when that value is a UUID. Anything else leaves the workspace empty.

Provider, endpoint, and MCP list queries include rows whose `workspace_id` is null when a workspace id is present. With no workspace id they return every row.

The OpenAI-compatible routes also accept `Authorization: Bearer cx_gw_ws_<secret>` and `Authorization: Bearer cx_gw_app_<app id>`.

## Files

- `app/ai_gateway/routes/provider_routes.py` — provider HTTP facade
- `app/ai_gateway/http/providers/application/` — one file per provider action
- `app/ai_gateway/routes/endpoint_routes.py` — endpoint HTTP facade, unmounted
- `app/ai_gateway/http/endpoints/application/` — one file per endpoint action
- `app/ai_gateway/routes/proxy_routes.py` — OpenAI-compatible ingress facade
- `app/ai_gateway/http/ingress/application/` — one file per ingress action
- `app/ai_gateway/services/gateway_service.py` — routing, guardrails, failover, inference logs
- `app/ai_gateway/routes/mcp_routes.py` — MCP HTTP facade
- `app/ai_gateway/http/mcp/application/` — one file per MCP action
- `app/ai_gateway/routes/log_routes.py` — log HTTP facade
- `app/ai_gateway/http/logs/application/` — one file per log action
- `frontend/src/modules/ai_gateway` — screen

## Pages

- [Providers](providers.md)
- [Ingress](ingress.md)
- [MCP servers](mcp.md)
- [Tools](tools.md)
- [Logs](logs.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
