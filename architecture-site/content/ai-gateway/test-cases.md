# Test cases

Run these in a workspace where you can open **AI Gateway**. Use a provider key you are allowed to store.

## Add a provider

Open **AI Gateway**. The heading should be **AI Gateway** and the subtitle should mention model governance and MCP. The **Providers** tab should be selected.

Choose **Add Provider**. The heading should be **Create Model Provider Service**. Leave the name empty and save. You should see `Provider name is required`.

Enter a name such as `Lab OpenAI`, choose a catalog and schema, choose OpenAI, and save without a duplicate name. You should see `Provider created successfully`. The row should appear in the table. Creating the same name again should show `Provider with name 'Lab OpenAI' already exists.`

## Discover and ping

On the provider form, choose **Discover Models** before entering a key. You should see `Please enter an API key before discovering models`.

Enter a key and discover again. A reachable provider should toast `Discovered {count} models in {latency}ms`. A bad key should toast `Discovery failed:` or `Failed to discover models`.

From the provider list, ping the saved provider. Success should toast `Connection successful` and include the latency. Failure should toast `Connection failed:` or `Ping failed`.

## Call a model

Send `POST /api/v1/ai-gateway/v1/chat/completions` with a model name that matches an active endpoint, and a single user message.

You should get a chat completion, and **Inference & Audit Logs** should gain a row for that endpoint. An unknown model with no active provider should return HTTP 404 `No active AI Model Endpoint found for model`.

`GET /api/v1/ai-gateway/v1/models` should list the active endpoint names. With an active provider and no endpoints yet, the first read should create `gpt-5.4-mini` and `gpt-5.6-sol`.

## Register an MCP server and run a tool

Open the **MCP** tab. The built-in servers `compassx_sql_warehouse`, `compassx_catalog_search`, `compassx_notebook_manager`, and `compassx_dashboard_manager` should be listed under `system.ai`.

Open `compassx_sql_warehouse`. You should see `execute_sql`, `list_warehouses`, `list_tables`, and `describe_table`. Run `list_warehouses`. You should see `Tool executed successfully` and a latency.

`POST /api/v1/ai-gateway/mcp/tools/call` with `tool_name` `list_schemas` should return the catalog schemas. `GET /api/v1/ai-gateway/mcp/servers/native_sql/tools` should report `Successfully retrieved tools from native MCP server 'compassx_sql_warehouse'`.

Choose **Register MCP Server**, leave the name empty, and save. You should see `MCP Server name is required`. Register a server with a unique name. You should see `MCP server registered and tools loaded`. Registering that name again should show `MCP server 'that name' already registered.`

## Logs and a member path

Open **Inference & Audit Logs**. After the chat call above, the table should show the endpoint. Before any call, the empty text is `No inference activity logged yet. Query the AI Gateway or run an agent to generate audit logs.`

`GET /api/v1/ai-gateway/logs/inferences?limit=50` should return the same newest-first rows. `GET /api/v1/ai-gateway/logs/tools` should include the `list_warehouses` call after the tool run.
