# Profiles

A deployment profile says where each platform service runs. The files are `compassx/profiles/local-dev.yaml`, `docker.yaml`, `kubernetes-local.yaml`, and `kubernetes-cloud.yaml`. `load_profile` resolves an explicit name, then `COMPASSX_PLATFORM_PROFILE`, then `local-dev`. A missing file raises `PlatformError` with `Deployment profile '{name}' not found at {path}. Available: {list}`.

`compassx profile use` writes the chosen name to `.compassx/active-profile` under the repo root. The CLI reads that file when the command has no `--profile` and the environment variable is unset.

Each service has a mode: `local`, `docker`, or `kubernetes`. A service omitted from the profile uses `defaults.mode`. `mode_for` returns that mode. `driver_for_runtime` returns `compute.overrides` for that runtime type, or `compute.driver`.

Opening the profile logs `platform: active profile '%s'` on `compassx.container`. The same step sets `COMPASSX_ENV` and `compute_settings.COMPASSX_ENV` to `cloud` when the profile name ends with `-cloud`, and to `local` otherwise.

## The four profiles

`local-dev` runs the backend and the frontend as local windowed processes (`{venv_python} app.py` in `backend`, `npm run dev` in `frontend`). Postgres, Redis, MinIO, Airflow, Enterprise Gateway, Prometheus, the Omnigent server, and MLflow run in Docker. The compute driver is `docker`. Compose uses `deployments/docker-compose/docker-compose.yml` plus `docker-compose.local-dev.yml`, project name `compassx`, and `ensure_images: true`. Required healthy services are postgres, redis, minio, airflow, enterprise-gateway, backend, frontend, and prometheus.

`docker` runs every listed service in Compose, including backend and frontend. The compute driver is `docker`. Required healthy services are postgres and minio.

`kubernetes-local` runs the services in Kubernetes, namespace `compassx`. Images are ensured, RBAC is ensured, and port-forwards are on. The exposed service is `frontend`. The profile comment says the developer reaches the UI at `http://localhost:18080`. Required healthy services are `frontend`. External services start empty. A name listed under `kubernetes.external_services` is not applied from a manifest. The operator supplies it, and the registry still resolves the name.

`kubernetes-cloud` uses namespace `compassx`, does not build or load images, ensures RBAC, and does not port-forward. `required_healthy` is empty.

## Endpoints

`compassx/services.yaml` is the endpoint table. Each service has a `local`, `docker`, and `kubernetes` host, port, and protocol. `YamlServiceRegistry.get_service` picks the row for that service's mode.

A host-perspective registry is for a process on the developer machine. Docker and Kubernetes services then use the `local` row, so health checks hit localhost ports and port-forwards. A container-perspective registry uses the Docker hostname or the cluster DNS name. `PlatformContainer.service_registry` is container perspective. `host_service_registry` and the health checker are host perspective. `from_files` defaults to host perspective when the backend's own mode is `local`, and container perspective otherwise.

An environment variable `COMPASSX_SERVICE_<NAME>_<MODE>_HOST` or `_PORT` overrides the YAML. The service name is uppercased and dashes become underscores.

`lookup.resolve` and `lookup.resolve_url` use one registry per process, built from the active profile. `try_resolve_url` returns the fallback string on any error so a config import does not crash. `try_resolve_url_container` resolves from container perspective. When that host is `localhost` or `127.0.0.1`, the first occurrence is replaced with `COMPASSX_HOST_GATEWAY`, default `host.docker.internal`. `reset_registry` clears the cached registry.

Unknown service text is `Unknown service '{name}'. Known services: {list}`. A service with no row for its mode is `Service '{name}' has no endpoint defined for mode '{mode}'`.

The services in the file are backend, frontend, postgres, redis, minio, minio-console, airflow, enterprise-gateway, jupyter-server, prometheus, mlflow, and omnigent-server. Local ports include backend `8000`, frontend `5173`, postgres `5433`, minio `9000`, airflow `8080`, enterprise-gateway `8888`, jupyter-server `8889`, prometheus `9090`, mlflow `5555`, and omnigent-server `6767`.
