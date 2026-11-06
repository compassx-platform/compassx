from datetime import datetime, timezone

from app.monitoring.resources.application.list_resources import list_resources
from app.monitoring.schemas import Overview


class BuildOverview:
    def __init__(self, resource_manager):
        self.resource_manager = resource_manager

    def execute(self) -> Overview:
        all_resources = list_resources(self.resource_manager)
        platforms = [item for item in all_resources if item.kind == "platform"]
        nodes = [item for item in all_resources if item.kind == "node"]
        services = [item for item in all_resources if item.kind == "service"]

        if nodes:
            total_used_mb = sum(n.memory_mb for n in nodes)
            total_limit_mb = sum(n.memory_limit_mb for n in nodes if n.memory_limit_mb > 0)
            mem_util = round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0
            cpu_util = round(sum(n.cpu_percent for n in nodes) / max(len(nodes), 1), 1)
            net_throughput = round(sum(n.network_in_kbps + n.network_out_kbps for n in nodes), 1)
        elif platforms:
            plat = platforms[0]
            total_used_mb = plat.memory_mb
            total_limit_mb = plat.memory_limit_mb or sum(s.memory_limit_mb for s in services if s.memory_limit_mb > 0) or total_used_mb
            mem_util = plat.memory_percent or (round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0)
            cpu_util = plat.cpu_percent
            net_throughput = round(plat.network_in_kbps + plat.network_out_kbps, 1)
        else:
            total_used_mb = sum(s.memory_mb for s in services)
            total_limit_mb = sum(s.memory_limit_mb for s in services if s.memory_limit_mb > 0) or total_used_mb
            mem_util = round((total_used_mb / total_limit_mb) * 100.0, 1) if total_limit_mb > 0 else 0.0
            cpu_util = round(sum(s.cpu_percent for s in services) / max(len(services), 1), 1)
            net_throughput = round(sum(s.network_in_kbps + s.network_out_kbps for s in services), 1)

        import psutil, os
        node_cores = sum(int(getattr(n, "cpu_cores", 0)) for n in nodes if getattr(n, "cpu_cores", 0) > 0)
        total_cores = node_cores or psutil.cpu_count(logical=True) or os.cpu_count() or 1
        total_nodes = len(nodes) or (1 if platforms or services else 0)

        return Overview(
            total_nodes=total_nodes,
            total_cores=int(total_cores),
            total_services=len(services),
            running_services=sum(item.status.lower() in {"healthy", "running"} for item in services),
            cpu_utilization=cpu_util,
            memory_utilization=mem_util,
            network_throughput_kbps=net_throughput,
            runtime=self.resource_manager.source,
            prometheus_connected=self.resource_manager.prometheus_connected,
            collected_at=datetime.now(timezone.utc),
        )


def build_overview(resource_manager) -> Overview:
    return BuildOverview(resource_manager).execute()
