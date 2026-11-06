# Test cases

A person or an agent runs these in the product, end to end. They are not code tests. Pass means the outcome below is what you see.

## Create a connection

Open API Ingestion. Create a connection named with a base URL you control, auth type None, and no secret.

You should see the toast `Connection '{name}' created.` and the connection detail page. The secret is not shown. Go back to API Connections and search for the name. You should see that connection.

## Add a job and run it

From that connection, create a job config. Path template `/health`, cron `0 * * * *`, param source static with no values, pagination none. Enable it if it is not already enabled. Choose **Run Now**.

You should see `Run started.` and a run id. Open the run list. You should see a run left at `running` from the trigger, and a second run that finishes. The finished run's status is `succeeded` when the URL returns HTTP 200, `failed` when the call fails, and `partial` when some parameter values succeed and others fail. Open the finished run. You should see one item for `__none__`, a bronze path, and the page count.

## Keep the secret off the page

Create a connection with auth type API Key (Header) and a secret. Open the connection again. Rotate the secret.

You should see `has_secret` implied by the page offering **Rotate Secret**, and you should never see the old or new secret value. The toast is `Secret rotated successfully.`

## Block a delete

Leave the job config enabled. Delete the connection.

You should see a toast with `Cannot delete connection` and the count of enabled job configs. The connection remains. Disable the job, delete the connection, and confirm `Delete Connection?`. You should land on API Connections without that connection, and the disabled job is gone with it.

## Reset and read history

On an enabled job that has already succeeded once, choose **Reset All Watermarks** and confirm **Reset**.

You should see `Watermark reset. Next run will re-fetch all data.` Trigger again. The new finished run starts without the previous cursor. Delete the job and confirm the warning. You should return to Job Configs, and that job's runs and watermarks are gone.
