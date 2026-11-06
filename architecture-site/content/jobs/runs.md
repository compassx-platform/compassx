# Runs

A run is one execution of a published version. Task rows start `queued`. The dag run id for a manual start is `compassx_manual_{16 hex}` and for a rerun `compassx_rerun_{16 hex}`. Each task gets an execution token scoped to the job owner and the workspace. The token is not returned to the browser. The scheduler receives the token ids and the task-run ids in the dag conf.

## Start, list, cancel, retry

`POST /api/v1/jobs/{id}/run` requires execute. No published version is 400, `Job has no published version. Publish first.` An archived job is 400, `Cannot run an archived job`. A missing spec is 400, `Published scheduler specification not found`. A missing notebook is 422, `Cannot run job; notebook does not exist: {path}`. Storage failing is 503, `Notebook storage is unavailable.` If the dag is not registered yet, the response is 409, `Job is still publishing. Wait for the scheduler to register it.` A scheduler failure rolls the new rows back and returns 502, `Could not start this run. Please retry.` The log is `Airflow trigger failed for job %s` at error, with the traceback. Success is 201 and includes the task rows.

`GET /api/v1/jobs/{id}/runs` requires browse. `limit` defaults to 50 and cannot exceed 200. `offset` defaults to 0. Newest start time is first. Each run includes its task rows.

`GET /api/v1/job-runs/{id}` requires browse on the owning job. A missing run, a run whose job is outside this workspace, or a bad id is 404, `Run not found`.

`POST /api/v1/job-runs/{id}/cancel` requires execute. Only `queued` or `running` can be cancelled. Otherwise 400, `Run is not in a cancellable state`. A missing spec or dag run id is 400, `Scheduler run correlation is missing`. A scheduler failure is 502, `Could not cancel this run.` and logs `Airflow cancel failed for run %s`. On success the run is `cancelled` and queued or running tasks become `skipped`.

`POST /api/v1/job-runs/{id}/rerun` requires execute and starts a new run from the current published version, with `parent_job_run_id` set to the original. No published version is 400, `Job has no published version`. A scheduler failure is 502, `Could not rerun this job.`

`POST /api/v1/job-runs/{id}/tasks/{task_key}/retry` requires execute. The latest try must be `failed` or `upstream_failed`. Otherwise 400, `Task is not in a retryable state`. A missing task is 404, `Task not found in this run`. The action appends a queued try, mints a new token, and if the run is `failed` sets it back to `running`. A scheduler failure rolls that back and returns 502, `Could not retry this task.`

## Callback

`POST /api/v1/webhooks/airflow/task-state` reads the raw body and checks `X-Compassx-Signature` with the Airflow callback secret. A missing signature is 401, `Missing Airflow signature`. A mismatch is 403, `Invalid Airflow signature`. The timestamp must be within 300 seconds. Older is 403, `Stale Airflow callback`. An unreadable timestamp is 422, `Invalid callback timestamp`.

The row is matched on dag run id, Airflow task id, and try number. No row logs `Webhook: no task_run found for dag_run_id=%s task=%s try=%s` at warning and returns `{status: not_found}`. An unknown state returns `{status: unknown_state}` and does not write. A known state updates the task. `running` sets `started_at` once. `success`, `failed`, `skipped`, and `upstream_failed` set `ended_at`. Unless the parent run is already `cancelled`, the parent state is recomputed from the latest try of each task: all success, any up for retry, any running or queued, or any failed. The response is `{status: ok}`.
