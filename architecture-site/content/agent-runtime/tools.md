# Tools

Agent runtime does not register an agent tool record. It does own one tool HTTP route, used by Nova while Nova is running inside a sandbox.

## Call

`POST /api/v1/agent-runtime/sandbox/tools`

The body is JSON with `name`, `arguments`, and `session_id`. The session can also be sent as `X-CompassX-Runtime-Session`. The caller sends `Authorization: Bearer` plus, for a gateway token, the workspace that token maps to. A raw workspace id can be sent as `X-Workspace-Id` when the token is not a `cx_gw_ws_` token.

`routes.py` reads the JSON and forwards to `http/sandbox/application/sandbox_platform_tool.py`, which calls `execute_platform_tool` in `sandbox_tools.py`.

## What you should see

A local-only name (`python_code`, `run_shell`, `list_files`, `read_file`, `write_file`) or any name that is not a platform tool returns HTTP 403 `Tool '{name}' cannot run on the host.`

A missing bearer token is HTTP 401 `Sandbox token required.` An unknown `cx_gw_ws_` token is HTTP 401 `Invalid gateway token.` Anything else without `X-Workspace-Id` is HTTP 401 `Invalid sandbox identity.`

A missing runtime session is HTTP 404 `Runtime session not found for this sandbox.` A session whose workspace does not match the token is HTTP 403 `Sandbox token does not match this session.` If the system database is down, the response is HTTP 503 `System database is unavailable.`

A valid call ensures the Nova agent for that workspace and runs the named tool through the agent tool executor. The response is that tool's result. An invalid JSON body is HTTP 400 `Invalid JSON body.` Any other failure is HTTP 500 with the error text, cut at 400 characters.

The tool names Nova may call on the host are the platform specs in `sandbox_nova/tools/platform.py`: `sql_warehouse`, `catalog`, `search_assets`, `catalog_editor`, `notebook_manager`, `dashboard_manager`, `mlflow`, `rag_search`, `visualization`, `invoke_agent`, and the plan and skill tools listed there.
