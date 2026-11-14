# Projects

Projects group runtime sessions. Rows are stored in `agent_runtime_projects` and in `~/.compassx/agent_runtime_projects.json`. The id is `arp_` plus 12 hex characters.

`routes.py` forwards each handler to one file under `http/projects/application/`. The service methods forward to `lifecycle/application/`.

## List and create

`GET /api/v1/agent-runtime/projects` uses the `workspace_id` query when it is sent, otherwise the workspace on the request. The query returns that workspace plus rows whose workspace id is null, newest `updated_at` first. A database failure logs `[AgentRuntimeService] Failed to query projects from DB, falling back to memory: %s` and returns the in-memory list with the same rule.

`POST /projects` returns HTTP 201. An empty name is HTTP 400 `Project name is empty.` A name longer than 80 characters is stored as the first 80. A database save failure logs `[AgentRuntimeService] Failed to save project to DB: %s` and the project still returns. Any other failure is HTTP 500 `Failed to create project: {error}`.

## Delete

`DELETE /projects/{project_id}` returns `{"deleted": true, "project_id": id}` when the project existed. A miss is HTTP 404 `Project '{id}' not found.` Sessions that pointed at the project stay, with `project_id` cleared. A database failure logs `[AgentRuntimeService] Failed to delete project from DB: %s`.
