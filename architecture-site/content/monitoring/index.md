# Monitoring

Product module. Live CPU, memory, network, and disk numbers for the running CompassX profile, plus the history of those numbers.

The HTTP router is `app.monitoring.routes.router` at `/api/v1/monitoring`. `MonitoringService` stays importable from `app.monitoring.service`. Each method forwards to one application type. The screen is `frontend/src/modules/monitoring`.

This module does not expose a tool.

## Code

- `backend/app/monitoring/routes.py` — HTTP edge. It builds `MonitoringService` through `composition.py` and maps a missing service or node to HTTP 404.
- `backend/app/monitoring/service.py` — facade. The resource manager stays on the instance, because health reads `resource_manager.prometheus_connected` and `resource_manager.source`.
- `backend/app/monitoring/resources/application/` — list resources and build the overview.
- `backend/app/monitoring/history/application/` — one series, all services, and all nodes.
- `backend/app/monitoring/infrastructure/prometheus_exporter.py` — the scrape body. `exporter.py` is the shim, so `app.monitoring.exporter.render_prometheus_metrics` still works.
- `backend/app/monitoring/schemas.py` — the response models. There is no second domain model and no SQLAlchemy in this module.

## Owns

Nothing in the account database or the system database. Samples live in the resource manager's metric repository, which is in memory unless that repository is Prometheus.

## Calls

`get_monitoring_resource_manager` returns `platform.monitoring_resource_manager`. That object, `MonitoringResourceManager` in `compassx/monitoring`, collects from the host, Docker, local processes, or Kubernetes and records samples. Those collectors stay in Platform. This module only reads them. A collector failure logs `Monitoring collector %s failed: %s`, `Docker monitoring is unavailable: %s`, or `Kubernetes monitoring is unavailable: %s` at warning on logger `compassx.monitoring.manager`.

## Topics

- [Resources](resources.md)
- [History](history.md)
- [Screen](screen.md)

## Test cases

[Test cases](test-cases.md) are the end-to-end checks for this module.
