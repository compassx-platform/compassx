# Screen

Open Jobs from the workspace navigation. The route is `w/{workspace}/{app}/jobs`. The heading is **Jobs**, with the line `Schedule notebooks, queries, and dashboards to run automatically.`

## List

Search uses the placeholder `Search jobs…`. Loading says `Loading jobs…`. A failed load says `Failed to load jobs. Check your connection.` An empty workspace says **No jobs yet** and `Jobs let you schedule notebooks, queries, and dashboards to run automatically.` **Create job** asks for a name, placeholder `e.g. Daily Asset Sync`, and an optional description. Success toasts `Job '{name}' created.` and opens that job.

The table shows name, schedule, last run, status, the last five runs, and duration. From a row you can start a run, pause, resume, archive, or delete. The toasts are `Run started for '{name}'.`, `Job paused.`, `Job resumed.`, `Job archived. Scheduled runs have stopped.`, and `Job deleted.`

## A job

`/jobs/{id}` is headed with the job name. **Run now** toasts `Run started.` Pause and resume toast `Job paused.` or `Job resumed.` Archive toasts `Job archived.` and returns to the list. Delete toasts `Job deleted.` Saving the draft toasts `Draft saved.` Publish toasts `Job published. Waiting for scheduler registration.` Editing the name toasts `Job updated.`

The schedule field accepts a five-field cron. The placeholder is `0 2 * * *`. A task asks for a display name, a task key such as `ingest_data`, a type, and a target. A notebook target placeholder is `/notebooks/my_notebook.ipynb`. Parameters are key and value rows.

The Runs tab with no runs says **No runs yet** and `Click Run now to trigger the first run.`

## A run

`/jobs/{id}/runs/{runId}` can cancel, rerun, or retry a task. The toasts are `Run cancelled.`, `New run started.`, and `Task retry queued.` A rerun navigates to the new run. No task rows say `No tasks recorded for this run.`
