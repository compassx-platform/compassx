# Logs

`/api/v1/ai-gateway/logs` reads the system database through `SystemSessionLocal`. The session is closed after the request. These routes do not use the account database dependency.

## Inference logs

`GET /logs/inferences` returns `InferenceLogResponse` rows from `ai_gateway_inference_logs`. Optional `endpoint_name` filters `endpoint_name`. `limit` defaults to 50 and must be from 1 to 200. Rows are newest `created_at` first. A workspace id keeps rows for that workspace and rows whose workspace id is null.

Chat completions write these rows from `GatewayService` after the provider call. The row stores the endpoint name, provider type, upstream model, request messages, tools, response text, token counts, cost, latency, status code, and error message. Cost uses `input_cost_per_1k_tokens` and `output_cost_per_1k_tokens` on the endpoint.

## Tool logs

`GET /logs/tools` returns `ToolLogResponse` rows from `ai_gateway_tool_logs`. Optional `tool_name` filters `tool_name`. The same limit and workspace rule apply. Newest rows come first.

`MCPExecutionProxy.execute_tool` writes these rows. A failed insert logs `Could not write tool execution audit log: %s`.
