# Compute

Compute keeps the all-purpose runtimes a workspace attaches to notebooks. A resource is a row in the system table `compute.compute_resources`. Starting it creates a Kubernetes deployment, or a platform runtime when `COMPASSX_PLATFORM_ENABLED` is on. Spark, Flink, Ray, and DuckDB are the runtime values.

The HTTP prefix `/api/v1/compute` is added in `main.py`. The router itself has no prefix. The same router also includes the Sandbox router, so sandbox paths share this prefix. Sandbox behavior stays in the Sandbox module.

This module does not register an agent tool. There is no Tools page. Notebook Manager, owned by Agents and implemented in Nova, starts kernels by calling this module.

## What stays public

`app.compute.routes.router` still defines `router` and every handler name. `create_compute_resource` and `list_compute_resources` stay importable from that module. `_kernel_catalog_api_url` stays importable from that module because Nova loads it there. Each handler forwards to one application type.

`ComputeResourceService`, `platform_enabled`, and `_run_async` stay on `app.compute.services.resource_service`. The top-level package `compute.resource_service` star-imports that module. Startup still does `from compute.resource_service import ComputeResourceService` and `from app.compute.services.workspace_defaults import ensure_workspace_default_resources`.

`ComputeManager`, profiles, Kubernetes client, pod specs, and log streaming stay in `app.compute.services`. The `compute.*` modules at `backend/compute` are shims onto those files. Do not add a package that shadows `routes`, `services`, or `models`.

The ORM class stays `ComputeResource` in `app.compute.models.compute_resources`. `app.models.compute_resources` star-imports it. The system schema is `compute`.

## Privileges

A request without a workspace context returns HTTP 400 `No workspace context. Address this endpoint under /w/<workspace>.`

Creating a resource requires the workspace admin. The creator then receives ownership of `Securable.compute(resource.id)`.

The workspace default (`is_default`) can be browsed and attached by any member. `BROWSE` and `USE_COMPUTE` return immediately for that row. `MANAGE` does not. Deleting a resource, including the default, requires `MANAGE`.

| Action | Privilege |
| --- | --- |
| List | `BROWSE`, and the default is always listed |
| Get status, metrics | `BROWSE` |
| Update, start, stop, logs, kernel info, start kernel | `USE_COMPUTE` |
| Delete | `MANAGE` |
| Create | workspace admin |
| Start, stop, or restart MinIO, Enterprise Gateway, or Airflow | workspace admin |

Profiles, health, runtime info, the service list, and the port-forward replies require a workspace member. They have no securable.

## Files

- `routes/router.py` — HTTP facade and the Sandbox include
- `shared/support.py` — caller, privilege check, error JSON, logger name `app.compute.routes.router`
- `profile/application/list_profiles.py`
- `health/application/health_check.py` and `runtime_info.py`
- `service_control/application/` — list services, control a service, port-forward replies
- `resource/application/` — one file per resource action
- `services/resource_service.py` — persistence and start/stop
- `services/workspace_defaults.py` — default DuckDB resource and default SQL warehouse
- `services/manager.py`, `runtimes.py`, `profiles.py`, `k8s_client.py`, `logs.py`, `config.py`

## Pages

- [Resources](resources.md)
- [Services and health](services.md)
- [Kernels](kernels.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
