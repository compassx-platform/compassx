# Services and health

These routes describe the cluster and the shared processes a compute pod depends on. They do not create a `compute_resources` row.

## Profiles

`GET /profiles` takes an optional `env` query. The default is `COMPASSX_ENV`. Local and cloud keep different availability.

| Profile | Label | Local | Cloud |
| --- | --- | --- | --- |
| `local` | Small (2GB • 1 vCPU) | available | unavailable |
| `cloud-xs` | Small (2GB • 1 vCPU) | available | available |
| `cloud-s` | Medium (4GB • 2 vCPU) | available | available |
| `cloud-l` | Standard (16GB • 4 vCPU) | unavailable | available |
| `gpu` | GPU (32GB • 4 vCPU • NVIDIA Dedicated) | unavailable | available |

The response includes `available`, `reason`, and `resources.requests` plus `resources.limits`. `get_available_profiles` returns unavailable profiles too, so the screen can show why one cannot be chosen. `get_profile` raises `ProfileNotAvailableError` `Unknown profile: {id}` or the profile's unavailable reason. The logger name is `app.compute.services.profiles`. The debug line is `Profile resolved: id={id} env={env}`.

## Health

`GET /health` picks a driver from the platform runtime manager when the platform flag is on. Otherwise it is `kubernetes` when `compute_settings.is_k8s()` is true, and `docker` otherwise.

Docker pings the local daemon with a 3 second timeout. Success is `{"status":"ok","driver":"docker","docker":"reachable"}` and debug `Docker: health check passed`. Failure is HTTP 503 with `status` `degraded`, `docker` `unreachable`, and message `Docker daemon not reachable. Ensure Docker Desktop is running.` The warning is `Docker: health check failed: {error}`.

`local` returns `{"status":"ok","driver":"local"}` without a probe.

Kubernetes lists one pod in `COMPASSX_NAMESPACE` or `compassx`. If that call fails, it asks the API for resources. Success is `{"status":"ok","driver":"kubernetes","kubernetes":"reachable"}` and debug `K8s: health check passed`. A timeout is HTTP 503, warning `K8s: health check timed out`, message `Kubernetes health check timed out.` Any other failure is HTTP 503, warning `K8s: health check failed: {error}`, and message `Kubernetes not reachable.` when the settings say this process is on Kubernetes. Otherwise the message is `Kubernetes not connected. Start minikube.`

## Runtime

`GET /runtime` returns the platform profile name, or `unknown` when `app.state.platform` is missing. `backend_url` comes from `try_resolve_url("backend", "http://localhost:8000")`. `compassx_env` is `COMPASSX_ENV`.

## Shared services

`GET /services` asks MinIO, Enterprise Gateway, and Airflow for status in parallel, with a 3 second wait. A failed check logs `compute-service: {id} status failed: {error}` and returns phase `error`, message `{label} status check failed.` A check that is still running logs `compute-service: {id} status timed out` and message `{label} status check timed out.`

`POST /services/{service_name}/{action}` accepts `minio`, `enterprise-gateway`, and `airflow`, and actions `start`, `stop`, and `restart`. An unknown service is HTTP 404 `Unknown compute service: {name}`. An unknown action is HTTP 400 `Unsupported action: {action}`. The caller must be a workspace admin. The reason string is `Controlling the {name} service`.

Airflow runs the action on a daemon thread and returns immediately with phase `starting` and message `{label} {action} requested.` The thread logs `compute-service: {name} {action} requested` and, on completion, `compute-service: {name} {action} completed phase={phase} message={message}`. A failure logs `compute-service: {name} {action} failed`.

MinIO and Enterprise Gateway run the action on the request. After MinIO `start` or `restart`, the route calls `ensure_buckets`. A failure is a warning `MinIO buckets ensure failed after {action}: {error}` and the status is still returned.

## Port forwards

`GET /services/port-forwards/status` returns `enabled` false, `forwards` empty, and message `Port-forwards are managed by the compassx CLI. Run: compassx status`.

`POST /services/port-forwards/recover` returns `enabled` false and message `Port-forwards are managed by the compassx CLI. Run: compassx up`.

## Pod shape

`build_pod_spec` in `services/runtimes.py` builds the container for the runtime. DuckDB rejects a profile outside the DuckDB set with `DuckDB is only valid with profiles: {names}`. An unknown runtime raises `Unknown runtime: {runtime}`. The pod name is `compassx-{runtime}-{job_id}`. A custom image replaces the builder image. The node selector comes from the account compute node pool when that lookup succeeds. The Kubernetes logger name is `app.compute.services.manager`. Creating a missing namespace logs `K8s: namespace {name} created`.
