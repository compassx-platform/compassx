# Platform

Platform is the process that starts CompassX and the place a user runtime is turned into a process, a container, or a pod. The package is `compassx`. Docker and Kubernetes stay behind drivers. The backend does not start Postgres, MinIO, Airflow, or Enterprise Gateway itself. The `compassx` command does.

`main.py` builds one `PlatformContainer` during startup and stores it on `app.state.platform`. It waits for the profile's required services, then serves. The wait skips `backend`, because the process cannot answer its own health check until startup finishes. The timeout is `COMPASSX_STARTUP_TIMEOUT`, default `5` seconds. Success logs `Platform services healthy: %s` at info. `HealthCheckFailedError` logs `Platform not healthy at startup:` at error and the process keeps serving so `/healthcheck` can still answer.

This module does not register an agent tool. There is no Tools page. Notebook, dashboard, SQL warehouse, and MLflow tools stay with Agents. The Omnigent server stays with Apps.

Platform stays in this process. Compute, Jobs, and Monitoring call the container, the runtime manager, and the collectors. They do not copy the drivers.

## What stays public

`compassx.cli.main` still defines `app` and the command names `up`, `down`, `restart`, `status`, `health`, `logs`, `profile_list`, and `profile_use`. Each command forwards to one file under `compassx/cli/application/`.

`PlatformManager` still defines `up`, `down`, `restart`, `status`, `health`, and `logs`. Each method forwards to one file under `compassx/platform_manager/application/`. The logger stays `compassx.platform_manager.manager`.

`services.enterprise_gateway.router`, `services.airflow.router`, and `services.jupyter_server.router` still define `router`. `main.py` mounts them at `/api/v1/services/enterprise-gateway`, `/api/v1/services/airflow`, and `/api/v1/services/jupyter-server`. Each handler forwards to one application file. The loggers stay `services.enterprise_gateway.router`, `services.airflow.router`, and `services.jupyter_server.router`.

`PlatformContainer`, `YamlServiceRegistry`, `load_profile`, the drivers, the launchers, `DefaultRuntimeManager`, and `MonitoringResourceManager` stay on their current import paths.

## Files

- `compassx/cli/main.py` — command facade
- `compassx/cli/application/` — one file per command
- `compassx/container.py` — one container per process
- `compassx/platform_manager/manager.py` — lifecycle facade
- `compassx/platform_manager/application/` — one file per lifecycle action
- `compassx/platform_manager/health.py` — checks and root-cause text
- `compassx/registry/` — profiles and `services.yaml`
- `compassx/lookup.py` — endpoint lookup for other modules
- `compassx/launchers/` — local process, Docker Compose, Kubernetes
- `compassx/drivers/` — local, Docker, and Kubernetes runtime drivers
- `compassx/runtime/` — runtime manager, resource manager, spec builders
- `compassx/monitoring/` — collectors the Monitoring module reads
- `services/enterprise_gateway/router.py` — Enterprise Gateway HTTP facade
- `services/airflow/router.py` — Airflow HTTP facade
- `services/jupyter_server/router.py` — Jupyter Server HTTP facade

## Pages

- [Profiles](profiles.md)
- [Command line](cli.md)
- [Lifecycle](lifecycle.md)
- [Launchers](launchers.md)
- [Drivers](drivers.md)
- [Runtimes](runtimes.md)
- [Monitoring collectors](monitoring.md)
- [Service HTTP](services.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
