# Tools

The gateway exposes tools in two ways. Built-in MCP servers register tools in process. `POST /api/v1/ai-gateway/mcp/tools/call` runs any tool the workspace can see, built-in or registered.

An agent or a person calls a tool with JSON `{"tool_name", "arguments", "caller_id", "server_id"}`. The response is `MCPToolCallResponse`. On the screen, open the MCP server, choose the tool, and run it. Success toasts `Tool executed successfully in {latency}ms`. A tool error toasts `Tool error: {message}`.

The same tools are also available over the MCP wire protocol on `/api/v1/ai-gateway/mcp/sse` and `/api/v1/ai-gateway/mcp/servers/{name}/sse`. A `tools/list` result comes back from `GET /mcp/servers/{name}/tools`. A `tools/call` result comes back from the JSON-RPC endpoint.

## compassx_sql_warehouse

Description: `Execute SQL queries, inspect tables/schemas, and manage CompassX SQL Warehouses.`

- `execute_sql` — `Execute a SELECT SQL query against the CompassX data warehouse and return rows (up to 1000).`
- `list_warehouses` — `List all available SQL Warehouses and their running status.`
- `list_tables` — `List accessible tables and views in the current catalog schema.`
- `describe_table` — `Describe column names, types, and constraints of a specific table.`

Aliases `native_sql` and `system.ai.compassx_sql_warehouse` reach this server.

## compassx_catalog_search

- `search_catalog` — `Search for data assets, tables, columns, dashboards, or notebooks matching a query keyword.`
- `list_schemas` — `List all schemas available in the data catalog.`
- `get_table_schema` — `Get detailed column definitions and metadata for a specific catalog table.`

Alias `native_catalog` reaches this server.

## compassx_notebook_manager

- `notebook_manage` runs `create_notebook`, `read_notebook`, `run_cell`, `edit_cell`, `add_multiple_cells`, `get_cell_output`, `get_variable_state`, `list_imports`, and `get_schema`. The description tells the caller to persist data with `cx.write_table(df, 'catalog.schema.table', mode='overwrite')`.
- `create_notebook` — `Create a new notebook in the specified catalog and schema.`
- `read_notebook` — `Read the cells and contents of a notebook by path or ID.`

## compassx_dashboard_manager

- `dashboard_manage` runs `list_dashboards`, `get_dashboard`, `create_dashboard`, `update_dashboard`, `add_dataset`, `update_dataset`, `delete_dataset`, `add_widget`, `update_widget`, `delete_widget`, `describe_widget`, `run_query`, and `publish_dashboard`.
- `list_dashboards` — `List all available dashboards in the workspace.`
- `create_dashboard` — `Create a new dashboard in CompassX.`

Notebook Manager and Dashboard Manager are also reached from Agents. The tool implementations for these four servers live in this module.
