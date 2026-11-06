# Lifecycle

`PlatformManager` starts services in profile order, waits for health, and reports status. The class stays in `compassx.platform_manager.manager`. `up`, `down`, `restart`, `status`, `health`, and `logs` each forward to `compassx/platform_manager/application/`.

Startup order is `startup_order`, limited to services that exist on the profile. Profile services missing from that list are appended. A requested subset keeps that order and drops names that were not requested.

Consecutive services that share a launcher run as one group. A mode with no launcher logs a warning, `platform: no launcher for mode '%s' (service %s); skipping`, and that service is left out.

`up` logs `platform: starting profile=%s services=%s`, calls `launcher.start` for each group, then waits. The wait list is `required_healthy` intersected with the services just started. If that intersection is empty, it waits on the services just started. The default timeout is `300` seconds. Readiness logs `platform: READY (profile=%s)`. The return value is a status snapshot that includes the health report.

`down` walks the same order in reverse, calls `launcher.stop`, and logs `platform: stopped (profile=%s)`.

`restart` calls `launcher.restart` in forward order and returns status without a health report.

`status` asks each launcher for its group and returns `PlatformStatus`. `ready` is true only when the service list is non-empty and every service is running.

`health` checks the requested names, or every ordered service when the caller passes none.

`logs` looks up the launcher for that service's mode. A missing launcher raises `LauncherError` with `No launcher available for mode '{mode}' (service '{service}')`.

## Health checks

`HealthChecker` uses the host registry. HTTP paths are backend `/healthcheck`, minio `/minio/health/live`, airflow `/health`, enterprise-gateway `/api`, jupyter-server `/api`, prometheus `/-/healthy`, frontend `/`, omnigent-server `/health`, and mlflow `/health`. Any other service, or a non-HTTP protocol, is a TCP connect. The connect timeout is `3` seconds. Each service is tried once plus `2` retries, with a backoff of `0.5` seconds times the attempt number.

An HTTP status below `500` is healthy. `500` and above is unhealthy, cause `http-{code}`, message `'{name}' responded {code} at {url}. Service is reachable but failing internally — check its logs: \`compassx logs {name}\`.`

Connection failures are classified:

- DNS: `Cannot resolve host '{host}'. If running on the host, the service mode for '{name}' may be wrong (docker/k8s hostname used outside its network). Check the active deployment profile.`
- Connection refused, including Windows error `10061`: `Connection refused at {host}:{port}. Service '{name}' is not listening — it may not be started yet. Run \`compassx up\` or check \`compassx status\`.` The Windows text omits "it may not be started yet" and says `run \`compassx up\` or check \`compassx status\`.`
- Timeout: `Timeout connecting to {host}:{port}. Service '{name}' may be starting, overloaded, or blocked by a firewall/proxy.`
- Anything else: `Failed to reach '{name}' at {host}:{port}: {exception class}: {exception}`

An unknown registry name returns cause `unregistered` and the registry's message. The last failed attempt logs a warning: `health.check failed service=%s endpoint=%s cause=%s attempts=%s: %s`.

`wait_until_healthy` polls every `3` seconds. On timeout it raises `HealthCheckFailedError` with `Platform services failed health checks after {seconds}s:` and the per-service summary. A summary line is `[OK]` or `[FAIL]`, the name, the endpoint, and the latency in parentheses when present. A failure's next line is `-> {message}`.
