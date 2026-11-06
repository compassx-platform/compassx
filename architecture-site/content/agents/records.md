# Records

`/api/v1/agents` stores the agent definition.

`GET /agents` lists agents in `guard.workspace_id`, ordered by name, then keeps only those the caller may `BROWSE`. Each row includes `tool_count`.

`POST /agents` returns HTTP 201. The caller must be a workspace admin. The row stores `created_by` as the principal id, `status` as the body value or `active`, and `manifest` as the body value or `{}`. Tools and skills on the body are replaced through `_sync_tools` and `_sync_skills`. The caller is recorded as the owner of `Securable.agent`.

`GET /agents/{agent_id}` returns the definition, including the prompt, for a caller who may `BROWSE`.

`PUT /agents/{agent_id}` requires `EDIT`. It writes the fields present on the body. When `tools` or `skills` is present, that set is replaced.

`DELETE /agents/{agent_id}` requires `MANAGE` and returns HTTP 204.

`POST /agents/{agent_id}/clone` requires `BROWSE` on the source. The guard message for the copy is `Cloning an agent`. It returns HTTP 201. The clone name is `{source name} (copy)`. The clone copies the prompt, model, tools, and skills, and the caller owns the new agent.

## Context

`/api/v1/agents/{agent_id}/context` stores extra context entries on the agent.

`GET` requires `BROWSE` and returns the entries. `POST` requires `EDIT` and returns HTTP 201. `PUT /{entry_id}` requires `EDIT`. `DELETE /{entry_id}` requires `EDIT` and returns HTTP 204. A missing entry is HTTP 404 `Context entry not found`.
