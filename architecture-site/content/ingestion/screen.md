# Screen

Open **API Ingestion** from the workspace navigation. It lands on `w/{workspace}/{app}/ingestion/connections`. The heading is **API Connections**, with the line `Reusable endpoint + auth configs for pull-based API ingestion`.

## Connections

Search filters the list. An empty workspace says **No connections yet** and `Create a connection to start ingesting data from a REST API.` **New Connection** asks for a name, a base URL, an optional description, an auth type, the non-secret auth field, and a secret. The secret label says it is encrypted at rest and never shown again. **Create Connection** is available once name and base URL are filled. Success is the toast `Connection '{name}' created.` and the connection detail page.

The detail heading is the connection name. **Rotate Secret** takes a new value and toasts `Secret rotated successfully.` **Delete** asks `Delete Connection?` and says disabled job configs that reference it will also be deleted, and that enabled configs block deletion. A blocked delete shows the API error in a toast. The page lists that connection's job configs, or `No job configs for this connection yet.`

## Job configs

`/ingestion/job-configs` is headed **Job Configs**. Search uses the placeholder `Search job configs…`. With no connections the empty text is `Create a Connection first, then add a Job Config.` Otherwise it is `Define your first pull — set path template, pagination, and schedule.` **New Job Config** is disabled until a connection exists.

The create form asks for a name, a connection, a path such as `/assets/{asset_id}/readings`, a cron such as `0 * * * *`, a param source, and static values as a comma-separated list. Success toasts `Job config '{name}' created.` and opens that config.

The detail heading is the config name, with **Enabled** or **Disabled**. **Enable** and **Disable** toast `Job config enabled.` and `Job config disabled.` **Run Now** is disabled while the job is disabled, with the title `Enable the job first`. A start toasts `Run started. ID: {first 8 chars}…`. **Edit** then **Save** toasts `Job config updated.` **Delete** warns that run history and watermarks will also be deleted.

The configuration card shows method, path template, cron, param source, pagination, cursor field path when one is set, and the bronze bucket. The watermark note says the watermark tracks how far each parameter has been ingested, and that resetting makes the next run re-fetch from the beginning. **Reset All Watermarks** asks `Reset Watermarks?` and then toasts `Watermark reset. Next run will re-fetch all data.` No runs yet says `No runs yet. Click Run Now to trigger a manual run.`

## A run

`/ingestion/runs/{id}` is headed **Run Detail**. A missing run says `Run not found.` The error summary, when present, is shown above the items. Filtering items by a status that none of them have says `No items with status '{status}'.` With no filter and no items it says `No items.`
