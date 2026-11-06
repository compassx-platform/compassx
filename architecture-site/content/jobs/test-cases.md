# Test cases

A person or an agent runs these in the product, end to end. They are not code tests. Pass means the outcome below is what you see.

## Create a job

Open Jobs. Create a job with a name and a short description.

You should see `Job '{name}' created.` and the job page. The job is active and still unpublished. Search for the name on the Jobs list. You should see that row.

## Publish a notebook task

Edit the draft. Add one notebook task whose key is lowercase, whose target is a notebook that exists in this workspace, and whose schedule is `0 2 * * *`. Save the draft, then publish.

You should see `Draft saved.` and then `Job published. Waiting for scheduler registration.` The unpublished marker clears. Publishing a task key that contains a space or a capital letter should show the task-key validation error and leave the draft unpublished.

## Run it

On the published job, choose **Run now**.

You should see `Run started.` Open the run. You should see one task row for that key, starting queued. If the scheduler has not registered the dag yet, you should see `Job is still publishing. Wait for the scheduler to register it.` and no new run row.

## Pause and resume

Pause the job, then resume it.

You should see `Job paused.` and then `Job resumed.` The list status follows. Pausing stops new scheduled starts. The published notebook must still exist before resume succeeds.

## Stop a run and start another

Open a queued or running run and cancel it. Then rerun from that run.

Cancel should toast `Run cancelled.` and the run should show cancelled. Tasks that had not finished should show skipped. Rerun should toast `New run started.` and open a new run that points back at the one you cancelled. A finished task that failed should offer retry, and retry should toast `Task retry queued.`
