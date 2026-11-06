# Connections

Database, LLM, git, and external connections are workspace credentials. A list keeps the rows the caller may `BROWSE`. A missing row in this workspace is HTTP 404 `Connection not found`. `USE_COMPUTE` is required to run through a connection. Seeing the row is not enough.

## LLM

`/api/v1/llm-connections` stores model credentials for agents.

`POST` returns HTTP 201. A save failure is HTTP 400 `Failed to save LLM connection: {error}`. Update failure is `Failed to update LLM connection: {error}`. `POST /{id}/set-embedding` marks the embedding connection. Its failure text is `Failed to set embedding LLM connection: {error}`. `DELETE` returns HTTP 204. `POST /{id}/ping` checks the saved credentials.

## Databases

`/api/v1/db-connections` stores database credentials and optional profiling.

`POST` returns HTTP 201 and may sync `sync_agent_db_connection` and start `trigger_profiling`. `PUT` does the same when the profiler fields change. `DELETE` returns HTTP 204 and clears the agent link. `POST /{id}/test` returns a ping result. `GET /{id}/schema` introspects the schema. A failure is HTTP 400 `Schema introspection failed: {error}`. `POST /{id}/reprofile` starts profiling again. With no profiler agent it is HTTP 400 `No profiler agent configured for this connection`. `GET /{id}/profiles` returns the saved profiles.

## Git

`/api/v1/git-connections` stores a Git provider and a token. `POST` returns HTTP 201. `DELETE` returns HTTP 204. `POST /{id}/test` calls `_test_github` or `_test_azure_devops` and returns `success` and `message`.

## External

External connections use both `/api/v1` paths and the unprefixed aliases on the same handlers. Create returns the new row. A bad body is HTTP 400 with the validation message. Get, update, disable, and delete use the connection id. A missing row is HTTP 404 with the service message. Disable does not delete the row.
