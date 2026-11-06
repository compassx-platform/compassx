# Test cases

These are product checks. Run them against a real profile and a workspace. Each case says what you do and what you should see.

## List profiles

Run `compassx profile list`.

You should see `docker`, `kubernetes-cloud`, `kubernetes-local`, and `local-dev`. The active profile has a `*` in front of it.

## Choose a profile

Run `compassx profile use not-a-profile`.

The process should exit with an error that starts `Deployment profile 'not-a-profile' not found`.

Run `compassx profile use local-dev`.

You should see `Active profile set to local-dev`. The next `compassx profile list` should mark `local-dev` with `*`.

## Start the local profile

Run `compassx up --profile local-dev`.

You should see `Starting platform with profile local-dev...` and a status table with columns Service, Running, Healthy, and Detail. When every row is running, the last line is `Platform ready.` If any row is not running, the last line is `Platform started (some services not running).`

## Status and health

With the platform up, run `compassx status`, then `compassx health`.

Status should print `Platform status — profile local-dev`. Health should print `Health — profile local-dev` with columns Service, Endpoint, Status, Latency, and Root cause. A service that is not listening should name the host and port and tell you to run `compassx up` or check `compassx status`. The health command exits `0` only when every row is healthy.

## Logs and stop

Run `compassx logs minio --tail 20`, then `compassx down --profile local-dev`.

Logs should print the MinIO output, or `<no logs>` when the launcher returns nothing. Down should print `Platform stopped.`

## Backend startup

Start the API while Postgres is stopped, with `COMPASSX_STARTUP_TIMEOUT` set to `5`.

The API log should contain `Platform not healthy at startup:`. `GET /healthcheck` should still return `{"status": "ok"}`. Start Postgres and the other required services, restart the API, and the log should contain `Platform services healthy:`.

## Docker runtime

Ask Compute to create a runtime on the `local-dev` profile, which uses the Docker driver.

The platform log should contain `runtime.create runtime_id=runtime-` and `Docker runtime created:`. Ask for an image that does not exist. You should get `Image not found: {image}`.

## Kubernetes without a cluster

Point the profile at `kubernetes-local` and create a runtime while the cluster is stopped.

You should see `Kubernetes not reachable. Run minikube start for local development.`

## Unknown runtime

Create a runtime whose type is not spark, flink, ray, duckdb, or notebook-job.

You should see `Unknown runtime type:` followed by the type and `Registered:`.

Create a DuckDB runtime with profile id `cloud-xl`.

You should see `DuckDB is only valid with profiles: cloud-s, cloud-xs, local`.

## Enterprise Gateway HTTP

`GET /api/v1/services/enterprise-gateway/status`.

You should receive `phase` and `message`. Stop Enterprise Gateway and `GET /api/v1/services/enterprise-gateway/kernels`. The status should be 503 and the body should be `error` `EGUnreachable`, `message` `Enterprise Gateway not reachable.`, `code` `503`.

## Airflow HTTP

Call `GET /api/v1/services/airflow/status`.

You should receive `phase`, `message`, and `details`.

## Jupyter Server HTTP

`POST /api/v1/services/jupyter-server/start`, then `GET /api/v1/services/jupyter-server/status`.

Start should return `phase` and `message`. Status should return the same two fields. If the manager cannot reach the cluster, the body is `InternalError` with HTTP 500.

## Monitoring row

Open Monitoring while `local-dev` is up and the collectors can see services.

The resource list should include a platform row named `CompassX (local-dev)`. It should read `Healthy` when every service is healthy or running, and `Degraded` when one is not.

## Platform shell

Sign in as a workspace admin and open `/w/{slug}/platform`.

The app switcher should offer Platform, Apps, and Portal. The sidebar should show Home, Notebooks, Jobs, Dashboards, Data Catalog, SQL Editor, SQL Warehouses, Query History, Agents, Agent Runtime, AI Gateway, Ontology, Connections, Compute, and Monitoring. The home title should be `Home`.

Sign in as a workspace viewer.

The switcher should offer Portal only.

Open Account Settings.

You should see the heading `Platform Services & Orchestration` and the label `Apache Airflow Webserver`.
