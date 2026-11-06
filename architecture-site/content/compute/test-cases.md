# Test cases

Run these in a workspace you can administer. A member who is not an admin can attach to the default resource and cannot create one.

## See the default resource

Open **Compute**. The heading should be **Compute**. The first tab should be **All-purpose Compute**.

You should see a resource named `default` with runtime DuckDB. Its phase should become running after the workspace is created. Opening it should show the resource name and a way back to **Compute**.

## Create a Spark resource

On **Compute**, choose **Create Compute**. The dialog title should be **Create Compute Resource**. Enter `Data Processing Pipeline`, choose Spark and a profile the environment marks available, and choose **Create Resource**.

The dialog should close and the new resource should appear in the table. It should be stopped until you start it. Creating it with a profile the environment marks unavailable should fail and the resource should not appear.

## Start, read logs, and stop

Start `Data Processing Pipeline`. The row should leave the stopped phase. Open the resource and read the logs.

You should see log lines once the pod is running. If the pod is not running yet, the logs request should say there is no running pod. Stop the resource. The row should return to stopped, and starting a notebook on it should wait until it is running again.

## Attach a notebook

Open a notebook and attach it to `default`, or to the Spark resource after it is running. Run a cell that reads a table you can browse.

You should get a kernel, the cell should run, and returning to **Compute** should still list that resource. Stopping the resource should disconnect the kernel. A member without `USE_COMPUTE` on a non-default resource should not get kernel info or logs for it. The same member should still attach to `default`.

## Shared services

Open the **Services** tab. You should see MinIO, Enterprise Gateway, and Airflow, or a timed-out row if a status check does not return within 3 seconds. The empty text, when the list is empty, is `No compute services found.`

As a workspace admin, restart MinIO. The row should show the new phase. As a member who is not an admin, the same restart should be refused.

## Health warning

Stop the cluster the process is configured to use, then open **Compute**.

You should see the health message above the toolbar. On Kubernetes that message is `Kubernetes not reachable.` or `Kubernetes not connected. Start minikube.` On Docker it is `Docker daemon not reachable. Ensure Docker Desktop is running.` Restoring the cluster and reloading should clear the warning.
