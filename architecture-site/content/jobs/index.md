# Jobs

Product module. A job is a scheduled graph of tasks. A person edits a draft, publishes an immutable version, and the scheduler runs that version. Each run is a row this module owns. Notebook tasks run in an ephemeral runtime.

The HTTP routers stay in `app.jobs.routes` and `app.jobs.execution_routes`.

- `/api/v1/jobs` and `/api/v1/job-runs` require a signed-in user.
- `/api/v1/webhooks/airflow` is the scheduler callback.
- `/api/v1/internal` is the operator protocol. It checks the internal secret.
- `/api/v1/job-executions` is how a task runtime asks to run and how it downloads a notebook.

Each route handler forwards to one application type. `recover_orphaned_executions` stays importable from `app.jobs.execution_service`. `reconcile_airflow_runs` stays importable from `app.jobs.reconciliation`.

This module does not expose a tool.

## Code

- `backend/app/jobs/routes.py` — job, run, and webhook HTTP. Helper names such as `_authorized_job` stay importable here and live in `shared/support.py`. Logs on these paths use logger `app.jobs.routes`.
- `backend/app/jobs/definition/application/` — list, create, update, delete, draft, publish, pause, resume, and archive.
- `backend/app/jobs/run/application/` — trigger, list, read, cancel, rerun, retry, and the Airflow task-state callback.
- `backend/app/jobs/task/application/` — prepare a scheduled task, exchange a token, start an execution, download the notebook, read execution status, and recover orphans.
- `backend/app/jobs/sync/application/reconcile_airflow_runs.py` — the poll that corrects run state. Its warning stays on logger `app.jobs.reconciliation`.
- `backend/app/jobs/execution_service.py` — the notebook executor and the task-type registry. Its failure logs stay on logger `app.jobs.execution_service`.
- `backend/app/jobs/assets.py` — the notebook lookup port. It reads catalog notebook rows.
- `backend/app/jobs/interfaces.py` — `SchedulerGateway`, the scheduler port.
- `backend/app/jobs/models/` and `schemas.py` — the system-database tables and the request models. There is no second domain model.

## Owns

System database tables in the `jobs` schema: `job`, `job_version`, `airflow_job_spec`, `job_run`, `task_run`, `execution_token`, `job_execution`, and `sync_correction`. Create issues `CREATE SCHEMA IF NOT EXISTS jobs` before the first insert.

## Calls

`get_scheduler_gateway` returns the process `SchedulerGateway`. When none is stored, it builds `AirflowSchedulerGateway` and keeps it on the app. Governance `Guard` checks `Privilege` on `Securable.job`. Notebook existence and bytes come from catalog storage through `assets.py`. A notebook task asks the platform runtime manager to create a `notebook-job` runtime.

## Topics

- [Definitions](definitions.md)
- [Runs](runs.md)
- [Execution](execution.md)
- [Screen](screen.md)

## Test cases

[Test cases](test-cases.md) are the end-to-end checks for this module.
