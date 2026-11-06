# Records

`GET /api/v1/apps` returns apps for the workspace, newest `created_at` first.

## Create

`POST /api/v1/apps` is HTTP 201. The slug is the body slug, or the name reduced to lowercase letters, digits, and hyphens. An empty slug becomes `app`. The route is the body route, or `/{slug}`, and gains a leading `/` when missing. Status is `active`. The git ref is `git_ref`, then `git_branch`, then `main`, and that value is stored in both `git_ref` and `git_branch`. A personal access token is encrypted and is not returned. `pat_configured` is true when the encrypted token is present.

The workspace identity is `id_app_` plus 12 hex characters, principal type `app_workload`, role `app_executor`, and scopes `catalog:read`, `compute:run`, `models:inference`, and `agents:invoke`. The log line is `Created app '{name}' (id={id}) for workspace '{workspace}'`.

After the row is committed, the route asks the ingress service to ensure an app ingress. A failure is a warning `Non-fatal app ingress initialization error for {slug}: {error}` and the app is still returned.

## Update and delete

`PUT /api/v1/apps/{app_id}` writes only the fields present on the body. A new git ref also replaces `git_branch`. A config object is flagged modified so SQLAlchemy stores it. A new token is encrypted. An empty token clears the stored value.

`DELETE /api/v1/apps/{app_id}` is HTTP 204. It asks the runner to delete the runtime. A cleanup failure is a warning `Error cleaning up app runtime for {id}: {error}` and the row is still deleted. The log line is `Deleted app '{name}' (id={id})`.

## Deploy

`POST /api/v1/apps/{app_id}/deploy` accepts optional `runner_mode` (`docker` or `local`) and `git_ref`. A ref that is not 1 to 128 characters of letters, digits, `.`, `_`, `/`, or `-` is HTTP 400 `Invalid git ref.`

The deployment id is `dep_` plus 10 hex characters. The runner returns runtime info and build logs. Kubernetes mode stores status `in_progress`. Any other successful mode stores `success`. A runner exception logs `App deployment failed for {name}: {error}`, stores status `failed`, and then returns HTTP 500 `Deployment failed: {error}` after the row is saved. The app status becomes `active` for success or in-progress, and `error` for failure.

The config keeps the newest 20 deployments, plus `logs` and `runtime`. A Kubernetes deploy also schedules `capture_deployment_build_logs` for that deployment id.

## Deployments, logs, and runtime

`GET /api/v1/apps/{app_id}/deployments` reconciles rows still marked `in_progress`, `building`, `starting`, or `queued`. A log line containing `[ERROR]`, `npm error`, `fatal:`, or `build failed` becomes `failed`. A line containing `[RUNTIME]`, `Build phase completed successfully`, `Launching application server`, or `Deployment, Service, and Ingress`, or an app status of `active`, becomes `success`. A success duration is rewritten when the stored duration is 2 seconds or less, capped at 60 seconds. A commit failure logs debug `Failed to commit reconciled deployment status for app {id}: {error}`.

`GET /api/v1/apps/{app_id}/deployments/{deployment_id}` uses the same reconciliation. A missing id is HTTP 404 `Deployment '{id}' not found.`

`GET /api/v1/apps/{app_id}/logs` returns live runner logs. `tail` defaults to 250. This route does not check the workspace.

`GET /api/v1/apps/{app_id}/runtime-status` returns the runner status. `POST /{app_id}/start` sets status `starting`, records app activity, and starts the runner. `POST /{app_id}/stop` sets status `stopping` and stops the runner.

`POST /api/v1/apps/{app_id}/status?status=` treats `stopped` and `inactive` as stop, and `active`, `starting`, and `provisioning` as start. Any other value is stored as given.

`/{app_id}/proxy/{path}` forwards the request to the running app and records activity. A missing app is HTTP 404 `App '{id}' not found.`
