# Skills, budgets, and logs

## Skills

`/api/v1/skills` is the skill library.

`GET` lists skills the caller can see. `POST` returns HTTP 201. A duplicate name is HTTP 400 `Skill with this name already exists`. `GET /{skill_id}` and `PUT /{skill_id}` use the same name check on update. A missing skill is HTTP 404 `Skill not found`. `DELETE /{skill_id}` returns HTTP 204.

`POST /{skill_id}/attach/{agent_id}` returns HTTP 201 and links the skill to an agent the caller may edit. `POST /{skill_id}/detach/{agent_id}` returns HTTP 204. A missing link is HTTP 404 `Attachment not found`.

## Budgets

`/api/v1/budgets` stores spend limits.

`GET` lists budgets. `POST` returns HTTP 201 and requires a workspace admin. The guard message is `Creating a budget`. A bad agent id is HTTP 400 `Invalid agent ID format: {id}`. A duplicate active period for the same scope is HTTP 400 `An active {period} budget already exists for {scope_type} {scope_id}`. A save failure is `Failed to save budget configuration: {error}`.

`GET /status` returns the current status of each budget. `PUT /{budget_id}` updates one. A conflicting active budget is HTTP 400 `Another active {period} budget already exists for this scope`. A missing budget is HTTP 404 `Budget configuration not found`. `DELETE /{budget_id}` returns HTTP 204. A delete failure is `Failed to delete budget configuration: {error}`.

## Streams and call logs

Active chat streams are under `/api/v1/streams`, described on the [Chat](chat.md) page. Model call rows are under `/api/v1/llm-calls`.
