"""Enterprise Gateway service manager — start/stop/restart/status."""
import logging
from datetime import datetime, timezone

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from compute.config import compute_settings
from compute.k8s_client import get_k8s_client
from services.base import BaseServiceManager, ServicePhase, ServiceResourceUsage, ServiceStatus
from services.enterprise_gateway.config import eg_settings
from services.enterprise_gateway.kernelspecs import build_kernelspec_configmap
from services.enterprise_gateway.manifests import build_eg_deployment, build_eg_service

logger = logging.getLogger(__name__)


class EnterpriseGatewayManager(BaseServiceManager):
    """Manages the Enterprise Gateway K8s Deployment."""

    def _ensure_namespace(self, namespace: str) -> None:
        k8s = get_k8s_client()
        try:
            k8s.core().read_namespace(name=namespace)
        except ApiException as exc:
            if exc.status == 404:
                ns = client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=namespace,
                        labels={"compassx/managed": "true"},
                    )
                )
                k8s.core().create_namespace(body=ns)
                logger.info("Created namespace %s", namespace)
            else:
                raise

    def start(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        env = compute_settings.COMPASSX_ENV
        self._ensure_namespace(namespace)
        k8s = get_k8s_client()
        apps = k8s.apps()
        core = k8s.core()

        # 1. Create/patch KernelSpec ConfigMap
        cm = build_kernelspec_configmap(namespace)
        try:
            core.create_namespaced_config_map(namespace=namespace, body=cm)
            logger.info("Created kernelspec ConfigMap")
        except ApiException as exc:
            if exc.status == 409:
                core.patch_namespaced_config_map(
                    name="compassx-kernelspecs", namespace=namespace, body=cm
                )
                logger.info("Patched kernelspec ConfigMap")
            else:
                raise

        # 2. Check if Deployment already running
        try:
            deploy = apps.read_namespaced_deployment(
                name="compassx-enterprise-gateway", namespace=namespace
            )
            if (deploy.status.available_replicas or 0) >= 1:
                return ServiceStatus(
                    phase=ServicePhase.RUNNING,
                    message="Enterprise Gateway is already running.",
                )
        except ApiException as exc:
            if exc.status != 404:
                raise

        # 3. Create Deployment
        deployment = build_eg_deployment(namespace, env)
        try:
            apps.create_namespaced_deployment(namespace=namespace, body=deployment)
            logger.info("Created EG Deployment")
        except ApiException as exc:
            if exc.status != 409:
                raise

        # 4. Create Service
        svc = build_eg_service(namespace)
        try:
            core.create_namespaced_service(namespace=namespace, body=svc)
            logger.info("Created EG Service")
        except ApiException as exc:
            if exc.status != 409:
                raise

        return ServiceStatus(phase=ServicePhase.STARTING, message="Enterprise Gateway starting.")

    def stop(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        k8s = get_k8s_client()
        apps = k8s.apps()
        core = k8s.core()

        for delete_fn, name in [
            (apps.delete_namespaced_deployment, "compassx-enterprise-gateway"),
            (core.delete_namespaced_service, "compassx-enterprise-gateway"),
        ]:
            try:
                delete_fn(name=name, namespace=namespace)
                logger.info("Deleted %s", name)
            except ApiException as exc:
                if exc.status != 404:
                    raise

        return ServiceStatus(phase=ServicePhase.STOPPED, message="Enterprise Gateway stopped.")

    def restart(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        apps = get_k8s_client().apps()
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            }
        }
        apps.patch_namespaced_deployment(
            name="compassx-enterprise-gateway", namespace=namespace, body=patch
        )
        return ServiceStatus(phase=ServicePhase.STARTING, message="Enterprise Gateway restarting.")

    def get_status(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        apps = get_k8s_client().apps()
        try:
            deploy = apps.read_namespaced_deployment(
                name="compassx-enterprise-gateway", namespace=namespace
            )
            available = deploy.status.available_replicas or 0
            if available >= 1:
                return ServiceStatus(phase=ServicePhase.RUNNING, message="Enterprise Gateway running.")
            return ServiceStatus(phase=ServicePhase.STARTING, message="Enterprise Gateway starting.")
        except ApiException as exc:
            if exc.status == 404:
                return ServiceStatus(phase=ServicePhase.STOPPED, message="Enterprise Gateway not deployed.")
            raise

    def get_resource_usage(self) -> ServiceResourceUsage:
        # Metrics API not guaranteed — return partial result
        return ServiceResourceUsage(metrics_available=False)


_eg_manager: EnterpriseGatewayManager | None = None


def get_eg_manager() -> EnterpriseGatewayManager:
    global _eg_manager
    if _eg_manager is None:
        _eg_manager = EnterpriseGatewayManager()
    return _eg_manager
