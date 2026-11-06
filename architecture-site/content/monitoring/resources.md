# Resources

A resource is one observed platform, node, or service. The kinds are exactly `platform`, `node`, and `service`. The resource manager collects them for the active deployment profile and caches the list for about a second, then refreshes in the background.

## List

`GET /api/v1/monitoring/nodes`, `/platform`, and `/services` call `MonitoringService.resources` with that kind. Each row is a `Resource`: id, name, status, runtime, uptime, CPU percent, memory percent and megabytes, memory limit, disk percent, network in and out in KB/s, restart count, health, start time, container name, and image version.

`GET /services/{resource_id}` and `GET /nodes/{resource_id}` return the one row with that id. A miss is HTTP 404 with `Service not found` or `Node not found`.

The profile also adds one platform row, id `platform:{profile}`, name `CompassX ({profile})`, by summing the services. Its status and health are `Degraded` when any service status or health is outside `healthy` and `running`. Otherwise they are `Healthy`.

## Overview

`GET /api/v1/monitoring/overview` folds the current list into one `Overview`.

When any node is present, CPU is the average of the nodes, memory utilization is used memory divided by the nodes' memory limits, and network throughput is the sum of each node's in and out rates. Node count is the number of nodes.

When there is no node, the first platform row supplies CPU, memory percent, and network throughput. Memory limit falls back to the sum of service limits.

When there is neither, the same totals are taken from the services. Node count is 1 when a platform or a service exists, and 0 when the list is empty.

`running_services` counts services whose status is `healthy` or `running`, ignoring case. `total_cores` uses a `cpu_cores` value on a node when one is present. The `Resource` response does not carry that field, so the core count falls back to the host's logical CPU count, then 1. `runtime` is the profile name. `prometheus_connected` is true only when the metric repository reports `connected`. `collected_at` is the time of this response.

## Health

`GET /api/v1/monitoring/health` always returns status `Healthy`. `prometheus` is `Connected` or `Disconnected`. `runtime` is the profile name. `message` is `Prometheus history is active` when the repository is connected, and `Prometheus is disconnected` otherwise.
