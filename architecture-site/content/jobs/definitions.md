# Definitions

A job belongs to one workspace. The list and every later lookup filter on that workspace before the grant check, so an id from another workspace is `Job not found`. A malformed id is the same 404, not a server error. The caller must hold the privilege named on each action. A run has no grant of its own. Access is the privilege on the job that owns it.

## Create and edit

`GET /api/v1/jobs` lists jobs the caller can browse. `search` matches the name. An unknown `status` is ignored. `POST /api/v1/jobs` requires a workspace admin. The body is a name and an optional description. The workspace and the owner come from the signed-in user, not from the body. The action creates version 1 as an empty unpublished draft and claims ownership of the job securable. The response is the job, with `has_unpublished_changes` true.

`GET /api/v1/jobs/{id}` requires browse. `PUT` requires edit and changes name and description when those fields are sent. `DELETE` requires manage and removes the job. The response is 204.

## Draft and publish

`PUT /api/v1/jobs/{id}/draft` requires edit. Every save appends a new `job_version` and points `draft_version` at it. Older drafts stay. The body carries cron, timezone, max active runs, retry policy, and task definitions.

`POST /api/v1/jobs/{id}/publish` requires edit. No draft is HTTP 400, `No draft version to publish`. A missing draft row is 404, `Draft version not found`.

Publish checks the spec before it writes:

- A cron, when set, must be five fields. Otherwise 422, `Schedule must be a five-field cron expression`.
- Every task needs a key matching `[a-z][a-z0-9_]{0,249}`. Keys must be unique. The graph must not contain a cycle or an unknown dependency.
- `task_type` must be `notebook`, `query`, or `dashboard_refresh`, and it must also be registered on the local executor. Today the registry contains `notebook`. Another type is 422, `No local-dev execution adapter is available for task type: {type}`.
- Each task needs a `target_ref`. Retry count is 0 through 10. Retry delay cannot be negative.
- Notebook targets must exist. Storage failing is 503, `Notebook storage is unavailable; publishing cannot be validated.` A missing notebook is 422, `Notebook does not exist: {path}`.

A passing publish marks that version published, sets `current_version`, clears `draft_version`, sets the job active, and upserts `airflow_job_spec`. The dag id is `compassx_job_{job_id}`. `publish_state` becomes `publishing` and `airflow_confirmed_at` is cleared. The checksum is the md5 of the canonical spec JSON.

`GET /api/v1/jobs/{id}/status` requires browse. No spec returns `{state: draft, confirmed_at: null}`. When the scheduler already has the dag, the action unpauses it only if the job is active, sets `publish_state` to `active`, and stamps `airflow_confirmed_at` the first time. A scheduler error logs `Could not confirm Airflow DAG %s` at warning and still returns the stored state. `GET /api/v1/jobs/{id}/version?which=published|draft` returns that version, or 404 `No {which} version found`.

## Pause, resume, archive

Pause and resume require edit. Pause sets status `paused`, marks the spec inactive, then asks the scheduler to pause the dag. A scheduler failure logs `Could not immediately pause Airflow DAG %s` at warning. The job stays paused. Resume checks published notebook targets first. Storage failing is 503, `Notebook storage is unavailable.` A missing notebook is 422, `Cannot resume job; notebook does not exist: {path}`. Otherwise the job becomes active, the spec becomes active, and the dag is unpaused. A failure logs `Could not immediately unpause Airflow DAG %s`.

Archive requires manage. Status becomes `archived` and the spec becomes inactive. Archive does not call the scheduler.
