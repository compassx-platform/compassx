# Screen

Open Monitoring from the workspace navigation. The route is `w/{workspace}/{app}/monitoring`. The heading is **Infrastructure Monitoring**, with the profile name beside it. The default profile label before the first response is `local-dev`.

The SQL warehouse page has its own monitoring tab for a warehouse. That tab is not this module.

## What loads

The page loads overview, services, and nodes together. Nodes failing to load leaves the node list empty and the rest of the page up. A failed overview or service list shows `Unable to connect to monitoring service.` The page refreshes on its own every 30 seconds. The control can be 5 seconds, 10 seconds, 30 seconds, or off. **Refresh** loads the live numbers again and, on the Metrics tab, the charts.

## Metrics

The Metrics tab is the default. The strip shows platform status, nodes, average CPU, memory utilization, and network throughput.

Platform status is **Healthy** when `running_services` equals `total_services`, and **Degraded** otherwise, with the counts in parentheses. The node label is **Cluster Nodes** when any node runtime contains `System`, and **Active Nodes** otherwise. The count is `total_nodes`, shown as 1 when that value is 0. CPU and memory are the overview percents. Network is `network_throughput_kbps` in KB/s.

The chart selector opens on **All Services (Stacked Comparison)**. **By Node (All Nodes Comparison)** calls `/monitoring/timeseries/nodes`. All Services calls `/monitoring/timeseries/services` for the four charts, and also loads each service's memory limit and the node CPU series. One service or one node calls `/monitoring/timeseries` for that id, plus memory limit for a single service. The charts are CPU Utilization, Memory Usage, Network Receive Rate, and Disk Read Rate. The ranges are **1h**, **6h**, **24h**, and **7d**. Timestamps can be local or UTC. A history call that fails leaves that chart empty and writes `Failed to load metric history from Prometheus` to the browser console.

## Services

The Services tab lists services. Search matches the service name or the container name. The status filter is All Statuses, Running Only, Stopped / Exited, Healthy, or Degraded. Running Only keeps status `running`. Stopped / Exited keeps every other status. Healthy and Degraded use the health field. An empty filter says `No services match your search or filter criteria.` Selecting a row opens that service. A later refresh keeps the same service open.
