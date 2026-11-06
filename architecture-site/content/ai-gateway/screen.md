# Screen

The screen is `AIGatewayPage` at `ai-gateway` inside the platform app. The shell title is `AI Gateway`. The page heading is **AI Gateway**. The subtitle is `Enterprise AI model governance, multi-vendor routing, rate limiting, and Model Context Protocol (MCP) tool hub.`

Tabs are **Providers**, **MCP**, and **Inference & Audit Logs**. The selected tab is the `tab` query: `providers`, `mcp`, or `logs`. **Refresh** reloads providers, MCP servers, tools, and inference logs. The search box placeholder is `Search {tab}...`.

The API client calls `/ai-gateway/providers`, `/ai-gateway/mcp/servers`, `/ai-gateway/mcp/tools`, `/ai-gateway/mcp/tools/call`, and `/ai-gateway/logs/inferences`. A load failure toasts `Failed to load AI Gateway data`, or the response `detail`.

## Providers

**Add Provider** opens the heading **Create Model Provider Service**. Editing opens **Edit Model Provider: {name}**.

The form requires a provider name, a catalog name, and a schema name. Empty values toast `Provider name is required`, `Catalog name is required`, or `Schema name is required`. Placeholders include `Enter Model Provider Service name`, `Select a catalog`, and `Select a schema`.

Provider choices on the form include OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, Ollama (Local), OpenAI-Compatible, AWS Bedrock, and Google Vertex AI.

**Discover Models** calls `POST /providers/discover-models`. With no API key the toast is `Please enter an API key before discovering models`, except for the automatic key path. Azure with no resource name or endpoint toasts `Please enter your Azure Resource Name or a valid Endpoint URL`. Success toasts `Discovered {count} models in {latency}ms`. Failure toasts `Discovery failed: {message}` or `Failed to discover models`. Adding a model name toasts `Model '{name}' added`. An empty model name toasts `Model name is required`.

Save toasts `Provider created successfully` or `Provider updated successfully`. A failure toasts the response `detail` or `Failed to save provider`. Ping success toasts `Connection successful ({latency}ms)`. Ping failure toasts `Connection failed: {message}` or `Ping failed`. Delete toasts `Provider deleted` or `Failed to delete provider`.

An empty provider table says `No AI model providers registered. Click 'Add Provider' to connect OpenAI, Anthropic, Gemini, Azure, or Ollama.`

## MCP

**Register MCP Server** opens **Register Model Context Protocol (MCP) Server**. Editing opens **Edit MCP Server: {name}**.

The name, catalog, and schema are required, with the same required toasts as providers, using `MCP Server name is required`. The endpoint placeholder is `http://localhost:8000/sse or https://mcp.internal.acme.com/sse`. The command placeholder is `npx -y @modelcontextprotocol/server-postgres postgresql://localhost:5432/db`. The description placeholder starts `e.g. Introspects relational databases`.

Create toasts `MCP server registered and tools loaded`. Update toasts `MCP server updated successfully`. A failure toasts the response `detail` or `Failed to save MCP server`.

Ping toasts `Connected ({latency}ms, {count} tools returned)` or `Endpoint connection failed`. Sync toasts `Synchronized {count} tools from {name}` or `Failed to sync MCP server`. Delete toasts `MCP server deleted` or `Failed to delete MCP server`.

An empty MCP table says `No MCP servers registered. Click 'Register MCP Server' to connect remote SSE or subprocess tools.`

Opening a server shows its name as the heading. The tools search placeholder is `Search {name} tools...`. Copying the endpoint toasts `Endpoint URL copied`. The displayed path is `/api/v1/ai-gateway/mcp/servers/{identifier}/tools`. Copying a response toasts `Response JSON copied to clipboard`.

Running a tool toasts `Tool executed successfully in {latency}ms`, `Tool error: {message}`, or `Execution failed: {message}`.

## Logs

The logs tab lists inference rows. An empty table says `No inference activity logged yet. Query the AI Gateway or run an agent to generate audit logs.`
