# Providers

`/api/v1/ai-gateway/providers` stores vendor connections in the account table `ai_providers`. The id is an integer. The API key is stored encrypted in `api_key_enc`. Responses expose `has_api_key` and `masked_api_key`. They do not return the plain key.

Provider types are `openai`, `anthropic`, `azure`, `gemini`, `bedrock`, `vertex`, `ollama`, and `compatible`. An unknown stored type is returned as `compatible`.

## List and create

`GET /providers` returns providers for the workspace plus providers with a null workspace id, ordered by name. With no workspace id it returns every provider.

`POST /providers` returns HTTP 201. A duplicate name in that same workspace scope returns HTTP 400 `Provider with name '{name}' already exists.` The stored type is the enum value. A body `api_key` is encrypted. `created_by` is the body value, or `X-User-Email`, or `X-User-Id`, or `system`.

## Read, update, delete

`GET /providers/{provider_id}`, `PUT`, and `DELETE` load by id only. A missing row is HTTP 404 `Provider not found`. Update writes only the fields present on `AIProviderUpdate`. An `api_key` value is encrypted. An empty `api_key` clears `api_key_enc`. Delete commits and returns HTTP 204.

A failed decrypt while building a response logs a warning `Could not decrypt api_key_enc for provider %s` and continues with no masked key.

## Discover and ping

`POST /providers/discover-models` does not write a row. It builds `ProviderCredentials` from the body and calls the adapter `ping`. The response is `success`, `message`, `latency_ms`, and `available_models`. An adapter exception logs `Error discovering models for provider %s: %s` and returns success false with `Discovery error: {error}`.

`POST /providers/{provider_id}/ping` loads the saved provider, decrypts the key when it can, and calls the same ping. A missing provider is HTTP 404 `Provider not found`. A decrypt failure uses a null key. An adapter exception logs `Ping error for provider %s: %s` and returns `Ping failed: {error}`.

## Endpoint records

`endpoint_routes.py` can list, create, update, delete, set-default, and set-embedding on `ai_model_endpoints`. `main.py` does not mount that router.

The paths that do run create endpoint rows in two places. `GET /api/v1/ai-gateway/v1/models`, when the workspace has no active endpoint and has an active provider, inserts `gpt-5.4-mini` and `gpt-5.6-sol`. The first is `is_default`. `GatewayService.resolve_endpoint`, when the requested model is missing and an active provider exists, inserts an endpoint whose name and upstream model are the requested name, or `gpt-5.4-mini` when the request asked for `default`, `default-chat`, or an empty model.
