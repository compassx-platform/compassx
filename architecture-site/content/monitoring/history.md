# History

History is the samples the resource manager stored for the active profile. The metric names are `cpu`, `memory`, `memory_limit`, `network_in`, `network_out`, `disk_read`, and `disk_write`. Units are `%` for CPU, `MB` for memory, and `KB/s` for network and disk.

## One resource

`GET /api/v1/monitoring/timeseries` requires `resource_type` (`platform`, `node`, or `service`), `resource_id`, and `metric`. `resolution` is the step in seconds, from 1 to 86400, default 60. When `end` is not after `start`, the window is the last 8 hours ending now. The body is the points the repository returned for that id, with `unit` taken from the metric.

## All services

`GET /api/v1/monitoring/timeseries/services` uses the same metric and window. `resolution` here is at least 60. The response has one series per current service, named and statused from the live resource, plus any history id that is not a current service, not a `k8s:node:` id, and not a `platform:` id. Those extra series are named from the id with `docker:`, `k8s:pod:`, and `compassx-` removed, then ` (Stopped)`, and their status is `Terminated`.

## All nodes

`GET /api/v1/monitoring/timeseries/nodes` keeps history ids that start with `k8s:node:`, or are `docker-host` or `local-host`, or match a current node id. A current node keeps its name and status. A `k8s:node:` id that is no longer current is named `Node {pool} (Scaled Down)` from the second `-` segment of the id, with status `Terminated`. If that filter matches nothing, the response is one empty series per current node.

## Scrape

`GET /api/v1/monitoring/export` is hidden from the OpenAPI schema. It asks the resource manager to refresh, then writes one Prometheus gauge, `compassx_resource_metric`, labeled with the profile, resource kind, resource id, and metric. The body is the Prometheus text format. The scrape uses the last completed snapshot, so it does not wait on a collector.
