# Execution

Scheduled work does not trust the browser token. Airflow calls the internal routes with `X-Compassx-Internal-Secret`. A mismatch is 403, `Invalid internal credential`.

## Prepare and exchange

`POST /api/v1/internal/job-tasks/prepare` loads the spec by dag id. No spec is 404, `Job specification not found`. An inactive spec, a missing job, or a job that is not `active` is 409, `Job is paused or inactive`. Missing notebook targets pause the job and the spec, try to pause the dag, and return 409, `Job was paused because its notebook does not exist: {path}`. Storage failing is 503, `Notebook storage is unavailable.`

The first prepare for a dag run inserts a `running` job run with trigger `scheduled` and one queued task row per resolved task. The named try becomes `running`. The action returns `task_run_id` and `token_ref`. It reuses an unexchanged, unexpired token for that task, preferring `token_ref` when that id parses, and mints one when none is usable.

`POST /api/v1/internal/execution-tokens/{token_ref}/exchange` locks the token row. A bad or unknown id is 404, `Execution token not found`. An already exchanged or expired token is 410, `Execution token is expired or already exchanged`. The response is the raw `access_token` and `expires_at`. The raw value is stored only as a hash.

## Run a task

`POST /api/v1/job-executions/run` requires `Authorization: Bearer {access_token}`. Missing is 401, `Missing execution token`. An unknown or expired hash is 403, `Invalid or expired execution token`. The task run must belong to that token's run and task key, or the response is 403, `Execution token scope mismatch`. If an execution already exists for the task run, the response is that execution and the token is not consumed again. A token already marked used is 403, `Execution token was already used`. The requested type and target must match the published task spec, or the response is 403, `Execution token is not scoped to this task target`. An unregistered type is 422 with the registry message.

A new execution is inserted as `queued`, the token is marked used, and the notebook executor is queued in the background. The response is 202, `{execution_ref, state: queued}`.

The notebook executor marks the execution `running`, starts runtime `job-exec-{id}` with profile `job`, and runs papermill inside it. The runtime downloads the notebook from `GET /api/v1/job-executions/{id}/notebook` using the same bearer token. That download checks the token scope and streams `application/x-ipynb+json`. A missing notebook task spec is 404, `Notebook task specification not found`. A non-notebook or a bad execution id is 404, `Execution not found` or the asset error. Success stores the last stdout line as `output_uri` and state `success`. Failure logs `Notebook job execution failed: %s` at error and stores `failed` plus the error trimmed to 10000 characters. Logs keep the last 100000 characters. The runtime is deleted afterward. A delete failure logs `Could not delete job runtime %s` at warning.

`GET /api/v1/internal/job-executions/{id}` requires the internal secret and returns state, output uri, and error. A missing row is 404, `Execution not found`.

## Recovery and reconciliation

On backend startup, `recover_orphaned_executions` marks every `queued` or `running` execution `failed` with `Execution interrupted because the backend restarted.` and deletes its runtime. A delete failure logs `Could not remove orphaned job runtime %s` at warning.

`reconcile_airflow_runs` polls runs that are `queued`, `running`, or `up_for_retry`. It writes a `sync_correction` when the scheduler's run or task state differs, and copies start and end times. A scheduler error logs `Could not reconcile Airflow run %s` at warning and continues with the next run.
