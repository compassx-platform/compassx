# Ingress

`/api/v1/ai-gateway/v1` is the OpenAI-compatible entry. `GatewayService` chooses an active `ai_model_endpoints` row, applies the rate limit and guardrails, calls the provider adapter, and writes an inference log.

## Caller

`Authorization: Bearer cx_gw_ws_<secret>` resolves the workspace through `workspace_id_for_gateway_token`. The caller type is `dev_agent` and the caller id is the workspace id. An unknown token is HTTP 401 `Invalid gateway token.`

`Authorization: Bearer cx_gw_app_<body>` treats a body that starts with `app_` as `app_` plus the next segment, and any other body as the text before the first `_`. It loads that `App` from the system database. A missing app is HTTP 401 `Invalid App Gateway Token: app '{id}' not found.` An archived app is HTTP 403 `Application is archived.` The caller type is `dev_agent` and the caller id is the app id.

Any other request uses the workspace id from the workspace context, `X-Workspace-Id`, or `workspace_id`. The caller type is `direct_api`. The caller id is `X-User-Id`.

## Chat completions

`POST /v1/chat/completions` accepts `ChatCompletionRequest`.

A streamed request returns `text/event-stream`. Each chunk is `data: {json}` and the stream ends with `data: [DONE]`. The headers are `Cache-Control: no-cache`, `Connection: keep-alive`, and `X-Accel-Buffering: no`. A stream error logs `Error during streaming SSE generation: %s` and emits `{"error": {"message": ..., "type": "gateway_error"}}` before `[DONE]`.

A non-stream request returns the chat completion. `ValueError` becomes HTTP 404 with that message. Any other exception logs `Chat completion error: %s` and becomes HTTP 502 with that message.

For a dev-agent caller, the user id passed to the service is the caller id. Otherwise it is `X-User-Id`. The caller id passed to the service is the resolved caller id or `body.user`.

## Responses

`POST /v1/responses` reads a JSON object. A non-object body is HTTP 400 `Responses body must be an object.` A missing model is HTTP 400 `Model is required.` The handler logs `Responses request model=%s stream=%s`.

String `input` becomes a user message. `instructions` becomes a system message. A `function_call` item becomes an assistant message with a tool call. A `function_call_output` item becomes a tool message. Items with a `role` are copied. Tools of type `function`, or with no type, are copied onto the chat request. `max_output_tokens` maps to `max_completion_tokens`.

A stream emits Responses events: `response.created`, text deltas, function-call argument deltas, and `response.completed`. A stream failure logs `Responses stream failed: %s` and emits an `error` event. A non-stream success returns `object: response`, `status: completed`, and an `output` list of message and function_call items. `ValueError` is HTTP 404. Any other exception logs `Responses completion error: %s` and is HTTP 502.

## Embeddings and models

`POST /v1/embeddings` sends the input texts to `GatewayService.embed`. A failure logs `Embedding generation error: %s` and returns HTTP 502. No embedding endpoint raises `No active embedding model endpoint configured in AI Gateway.`

`GET /v1/models` lists active endpoints for the workspace, including null-workspace rows. Each item uses the endpoint name as `id` and includes `provider_type`, `is_default`, and `use_for_embedding`.

## Routing inside GatewayService

`resolve_endpoint` keeps active endpoints in the workspace scope. It matches an integer id, then the endpoint name, then `upstream_model_name`. The names `default` and `default-chat` use the default endpoint, or the first active endpoint.

The rate-limit key is `{workspace or global}:{endpoint id}`. A limit failure raises `Rate limit exceeded: {current}/{limit} requests per minute.` or `Token rate limit exceeded: {current}/{limit} tokens per minute.` Chat estimates 500 tokens for that check.

When `guardrail_config` is set and `pii_masking` is not false, message text is masked as `[REDACTED_EMAIL]`, `[REDACTED_CREDIT_CARD]`, `[REDACTED_SSN]`, `[REDACTED_PHONE]`, or `[REDACTED_SECRET]`.

The call tries the primary endpoint, then each active id in `fallback_endpoint_ids`. A failed provider logs `Endpoint %s (provider %s) failed during streaming: %s. Attempting fallback...` or `Endpoint %s (provider %s) failed: %s. Attempting fallback...`. A missing endpoint raises `No active AI Model Endpoint found for model '{model}'`.

A successful or failed attempt writes `ai_gateway_inference_logs` on the system database. A log failure warns `Could not record AI Gateway inference log: %s`. A decrypt failure warns `Failed to decrypt API key for provider %s: %s`.
