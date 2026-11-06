# Sandbox

Sandbox runs a short-lived workspace for an app, an agent, a notebook, a job, or a custom task. The record is a `SandboxInstance` kept in memory on `sandbox_service`, plus whatever the active driver can discover. There is no sandbox table.

The router prefix is `/sandboxes`. `main.py` mounts that router at `/api/v1` and again at `/api/v1/compute`. The Compute router also includes it, so the same paths answer under `/api/v1/compute/sandboxes`. These routes do not check a privilege.

This module does not register an agent tool. There is no Tools page. The Agents Python tool runs a local subprocess. It does not call this module.

## What stays public

`app.sandbox.routes.router` still defines `router`, `ExecRequestBody`, and every handler name. `SandboxService` and the singleton `sandbox_service` stay on `app.sandbox.service`. `_normalize_key` stays importable from that module. Each service method and each route forwards to one application type.

`SandboxSpec`, `SandboxInstance`, `SandboxStatus`, `ExecResult`, `InitScript`, and `StorageMount` stay in `app.sandbox.models`. `BaseSandboxDriver` and `SandboxHandle` stay in `app.sandbox.interfaces`. Drivers stay in `app.sandbox.drivers`. `_sanitize_k8s_name` and `_sanitize_k8s_label_key` stay on `app.sandbox.drivers.k8s_driver`.

`app.sandbox` still exports those names and `sandbox_router`.

## Driver

`SandboxDriverFactory.get_driver` reads `runtime_mode` on the spec, or the active ingress mode when the spec leaves it empty. `k8s` and `kubernetes` use `KubernetesSandboxDriver`. `docker` uses `DockerSandboxDriver`. Anything else uses `LocalSandboxDriver`. One driver object is cached per mode.

The local driver stores each sandbox under `~/.compassx/sandboxes/{id}`. Kubernetes pods and services are named `compassx-sb-{sanitized id}` in `COMPASSX_NAMESPACE` or `compassx`. Creating that namespace logs `Created K8s namespace: {name}` on `app.sandbox.drivers.k8s_driver`.

## Files

- `routes.py` — HTTP facade
- `service.py` — `SandboxService` and `sandbox_service`
- `http/application/` — one file per route
- `lifecycle/application/` — one file per service action
- `shared/support.py` — `_normalize_key` and logger name `app.sandbox.service`
- `drivers/` — local, docker, and kubernetes
- `models.py`, `interfaces.py`

## Pages

- [Lifecycle](lifecycle.md)
- [Commands and terminal](commands.md)
- [Screen](screen.md)
- [Test cases](test-cases.md)
