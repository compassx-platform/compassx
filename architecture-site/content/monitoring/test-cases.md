# Test cases

A person or an agent runs these in the product, end to end. They are not code tests. Pass means the outcome below is what you see.

## Open the monitoring screen

Open Monitoring from the workspace navigation.

You should see **Infrastructure Monitoring**, the profile name, the Metrics tab, and the summary strip for platform status, nodes, average CPU, memory utilization, and network throughput. The page refreshes on its own.

## Read the services

Open Services. Search for a service name you can see. Filter to Running Only, then to Stopped / Exited when every service is running.

You should see the matching service, then only services whose status is `running`, then `No services match your search or filter criteria.` Clearing the filter brings the list back. Select a row and wait for a refresh. The same service stays open.

## Change the chart window

On Metrics, switch the range from **1h** to **24h**, then choose **By Node (All Nodes Comparison)**, then one service.

You should see CPU Utilization, Memory Usage, Network Receive Rate, and Disk Read Rate redraw for that window. By Node shows a series per node. One service shows that service only. If Prometheus is disconnected, the strip still shows the live numbers and an empty history chart does not remove them.

## Refresh by hand

Set auto-refresh to Off. Choose Refresh.

You should see the summary and the service list update once, and they should not keep updating until you turn auto-refresh back on or choose Refresh again.

## Ask for a missing resource

Request `GET /api/v1/monitoring/services/{id}` with an id that is not in the service list. Do the same for a node.

You should see HTTP 404, `Service not found` for the service and `Node not found` for the node.

## Scrape the metrics

Request `GET /api/v1/monitoring/export`.

You should see Prometheus text that includes `compassx_resource_metric`, with the current profile and one sample per resource and metric. This path is not listed in the API schema.
