# Monitoring collectors

`MonitoringResourceManager` in `compassx.monitoring` observes hosts, processes, containers, and pods. The Monitoring module reads this object from `app.state.platform.monitoring_resource_manager`. It does not collect on its own. The logger is `compassx.monitoring.manager`.

The container builds it with the Prometheus URL from the registry (`prometheus`) and a 3 second cache. `PrometheusMetricRepository` is the history store. A failed Prometheus query logs `Prometheus history query unavailable: %s` or `Prometheus grouped history query unavailable: %s` at warning and does not raise.

Which collectors run depends on the profile. `local-dev` uses `HostCollector` and `DockerComposeCollector` for the compose project. If Docker cannot be imported, it logs `Docker monitoring is unavailable: %s` and returns the host collector only.

Any other profile adds collectors for the modes it actually uses. `local` adds the host and `LocalProcessCollector`. `docker` adds the host and `DockerComposeCollector`, with the same warning if Docker is unavailable. `kubernetes` adds `KubernetesCollector` for `profile.k8s_namespace`. A failure logs `Kubernetes monitoring is unavailable: %s`.

`resources` returns the last sample. An empty cache, or a cache interval of `0`, collects on the caller. Otherwise a stale cache starts a daemon thread named `compassx-monitoring-refresh` and the caller gets the previous sample. A collector exception logs `Monitoring collector %s failed: %s` and the other collectors are kept.

When at least one observed item has kind `service`, the manager appends one platform row. Its id is `platform:{profile name}` and its name is `CompassX ({profile name})`. Status and health are `Healthy` when every service status and health are `healthy` or `running`, ignoring case. Otherwise they are `Degraded`. CPU and memory percents are the sums, capped at `100`. Memory, network, and disk rates are sums. Uptime on that row is `-`.

Metric names are `cpu`, `memory`, `memory_limit`, `network_in`, `network_out`, `disk_read`, and `disk_write`. Units are `%`, `MB`, `MB`, `KB/s`, `KB/s`, `KB/s`, and `KB/s`. `timeseries` and `timeseries_grouped` read those names back from the repository. An unknown metric name raises `KeyError`.
