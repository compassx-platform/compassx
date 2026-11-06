# Test cases

Run these in a workspace where you can create a notebook in a schema, and where one compute resource is the workspace default. Use a second user who cannot browse that schema when a case says so.

## Create from the list

Open **Notebooks**. You should see the heading **Notebooks**. Choose **New Notebook**. The dialog title should be **Create New Notebook**. Enter `data_transformation`, pick a catalog and a schema, and choose **Create Notebook**.

The editor should open on a notebook named `data_transformation`. Go back to **Notebooks**. The new notebook should be in the list. Creating it again with the same catalog, schema, and name should show that it already exists.

## Someone who cannot browse the schema

Sign in as a user with no `BROWSE` on that schema. Open **Notebooks**.

The new notebook should not be on the list. Opening its file path should be 404 `Notebook not found in catalog`.

## Edit and reload

In the editor, change a cell and save. Reload the notebook.

The cell text should still be there. The info panel should show **Created**. The response metadata should include the notebook id and the last compute resource, which is empty until you connect one.

## Path that leaves the folder

Request a notebook path that contains `..`.

You should get 400 `Invalid path` when the server turns that path into a storage key.

## Connect a kernel

On the workspace default compute resource, start a kernel from the notebook.

The kernel should start, and the notebook should remember that resource. Reload the notebook. It should offer to reconnect to the same resource and kernel name. A user who cannot use a non-default resource should get 404 `kernel not found` when they ask for a kernel on that resource.

## Stop and restart

Restart the kernel from the toolbar. The kernel should come back, and the editor should still be on the same notebook.

Stop the kernel. A following channel connection for that kernel id should close.

## Experiments

Run a cell that logs an MLflow run under the notebook path. Open the experiments panel.

You should see the run, with its status and metrics. The filter box placeholder is `Filter runs by name, param, metric...`. If MLflow is not running, the panel should say the tracking server is not reachable, and the notebook should stay editable.

## Register a model

From a run that wrote a `model` artifact, register it as `churn_classifier`.

You should get a version and a UI link. The models list should include `churn_classifier`. The search placeholder is `Search registered models, stages, aliases...`.

## Delete

Delete the notebook from the list.

It should leave **Notebooks** and the catalog schema. Opening the old path should be 404 `Notebook not found in catalog`.
