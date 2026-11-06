# Test cases

Run these in a workspace where you can browse and edit a schema, and where one SQL warehouse is running. Use a second user who cannot browse that schema when a case says so.

## Create from the list

Open **Dashboards**. You should see the heading **Dashboards**. Choose **Create Dashboard**. The name should already be `untitled_dashboard_1` or the next free number. Pick a catalog and a schema and submit.

You should see `Created dashboard "{name}"`. The new card should appear on the list. Open it. The canvas should show one page named **Page 1** and no widgets.

## Someone who cannot browse the schema

Sign in as a user with no `BROWSE` on that schema. Open **Dashboards**.

The new dashboard should not be on the list. Requesting `GET /api/v1/dashboards/{id}` as that user should be 404 `Dashboard not found`.

## Save a dataset and a widget

In the editor, add a dataset whose SQL reads a table you can query, save it, and put a table widget on the page.

You should see `Dataset saved`. Reload the canvas. The widget and the dataset should still be there. The warehouse query history should show a run with source `dashboard`.

## Query with a parameter

Give the dataset SQL that contains `:region`. From the canvas, set the parameter to `O'Brien`.

The widget should return the rows for that value. The SQL that reached the warehouse should contain `'O''Brien'`, not the raw quote. A parameter name such as `region;drop` should be 400 `Invalid parameter name: region;drop`.

## SQL override

As a viewer who can browse but not edit, call the dataset query endpoint with a different `sql` body.

You should be refused. As an editor, the same call should run the override and return `columns`, `rows`, `rowCount`, and `executionMs`.

## Schema, export, and field values

Open the dataset schema. You should see the stored columns, or one `{ name, type: "unknown" }` per column of a `LIMIT 0` query.

Export CSV. The download should be named `dataset.csv` and the first line should be the column names. Ask for field values of one column. You should get at most 1,000 distinct values. A field name that contains a quote should be 400 `Invalid field name`.

## Publish and discard

Publish from the top bar. You should see `Dashboard published`, and the document should no longer be a draft.

Change a widget title and discard. Confirm the dialog that says it will restore the last published version. You should see `Draft discarded`. The document should be a draft again, and the widget title you just typed should still be there.

## Clone and delete

Clone from the list. You should see `Cloned "{name}"`. The copy should be named `{name} (copy)`, should be a draft, and should have its own page and dataset ids. Editing the copy should not change the original.

Delete the copy. You should see `Deleted "{name}"`. It should leave the list and the catalog schema.

## No running warehouse

Stop every SQL warehouse and refresh a widget.

You should see a query failure whose message is `No running SQL warehouse is available for dashboard queries.`

## Share

Click **Share** on the top bar. You should see `Share coming soon`. Nothing should be copied or emailed.
