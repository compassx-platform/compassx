"""Health check for Enterprise Gateway service."""
import logging
from dataclasses import dataclass, field

import httpx
from kubernetes.client.exceptions import ApiException

from compute.k8s_client import get_k8s_client
from services.enterprise_gateway.config import eg_settings

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    healthy: bool
    api_reachable: bool
    kernelspecs_loaded: int
    active_kernels: int
    message: str
    details: dict = field(default_factory=dict)


async def check_eg_health(namespace: str) -> HealthStatus:
    """Check EG deployment + API reachability."""
    # 1. Check Deployment has availableReplicas > 0
    apps_api = get_k8s_client().apps()
    try:
        deploy = apps_api.read_namespaced_deployment(
            name="compassx-enterprise-gateway",
            namespace=namespace,
        )
        available = deploy.status.available_replicas or 0
        if available == 0:
            return HealthStatus(
                healthy=False,
                api_reachable=False,
                kernelspecs_loaded=0,
                active_kernels=0,
                message="Enterprise Gateway deployment has 0 available replicas.",
            )
    except ApiException as exc:
        if exc.status == 404:
            return HealthStatus(
                healthy=False,
                api_reachable=False,
                kernelspecs_loaded=0,
                active_kernels=0,
                message="Enterprise Gateway deployment not found.",
            )
        raise

    # 2. HTTP GET to EG /api endpoint via K8s service DNS
    eg_url = (
        f"http://compassx-enterprise-gateway.{namespace}.svc.cluster.local"
        f":{eg_settings.EG_PORT}"
    )
    kernelspecs_count = 0
    active_kernels = 0
    api_reachable = False

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            api_resp = await http.get(f"{eg_url}/api")
            api_reachable = api_resp.status_code == 200

            if api_reachable:
                ks_resp = await http.get(f"{eg_url}/api/kernelspecs")
                if ks_resp.status_code == 200:
                    ks_data = ks_resp.json()
                    kernelspecs_count = len(ks_data.get("kernelspecs", {}))

                k_resp = await http.get(f"{eg_url}/api/kernels")
                if k_resp.status_code == 200:
                    active_kernels = len(k_resp.json())
    except Exception as exc:
        logger.debug("EG health HTTP check failed: %s", exc)

    healthy = api_reachable
    message = "Enterprise Gateway is healthy." if healthy else "Enterprise Gateway API not reachable."

    return HealthStatus(
        healthy=healthy,
        api_reachable=api_reachable,
        kernelspecs_loaded=kernelspecs_count,
        active_kernels=active_kernels,
        message=message,
    )
