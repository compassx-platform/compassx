"""Jupyter Server service manager — start/stop/restart/status."""
import logging
from datetime import datetime, timezone

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from compute.config import compute_settings
from compute.k8s_client import get_k8s_client
from services.base import BaseServiceManager, ServicePhase, ServiceResourceUsage, ServiceStatus
from services.enterprise_gateway.config import eg_settings
from services.enterprise_gateway.manager import get_eg_manager
from services.jupyter_server.manifests import (
    build_jupyter_server_deployment,
    build_jupyter_server_service,
)

logger = logging.getLogger(__name__)


class JupyterServerManager(BaseServiceManager):
    """Manages the Jupyter Server K8s Deployment."""

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
            else:
                raise

    def start(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        env = compute_settings.COMPASSX_ENV
        self._ensure_namespace(namespace)

        # Ensure EG is running first
        eg_status = get_eg_manager().get_status()
        if eg_status.phase == ServicePhase.STOPPED:
            get_eg_manager().start()

        k8s = get_k8s_client()
        apps = k8s.apps()
        core = k8s.core()

        # Check if already running
        try:
            deploy = apps.read_namespaced_deployment(
                name="compassx-jupyter-server", namespace=namespace
            )
            if (deploy.status.available_replicas or 0) >= 1:
                return ServiceStatus(
                    phase=ServicePhase.RUNNING,
                    message="Jupyter Server is already running.",
                )
        except ApiException as exc:
            if exc.status != 404:
                raise

        deployment = build_jupyter_server_deployment(namespace, env)
        try:
            apps.create_namespaced_deployment(namespace=namespace, body=deployment)
        except ApiException as exc:
            if exc.status != 409:
                raise

        svc = build_jupyter_server_service(namespace, env)
        try:
            core.create_namespaced_service(namespace=namespace, body=svc)
        except ApiException as exc:
            if exc.status != 409:
                raise

        return ServiceStatus(phase=ServicePhase.STARTING, message="Jupyter Server starting.")

    def stop(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        k8s = get_k8s_client()
        apps = k8s.apps()
        core = k8s.core()

        for delete_fn, name in [
            (apps.delete_namespaced_deployment, "compassx-jupyter-server"),
            (core.delete_namespaced_service, "compassx-jupyter-server"),
        ]:
            try:
                delete_fn(name=name, namespace=namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise

        return ServiceStatus(phase=ServicePhase.STOPPED, message="Jupyter Server stopped.")

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
            name="compassx-jupyter-server", namespace=namespace, body=patch
        )
        return ServiceStatus(phase=ServicePhase.STARTING, message="Jupyter Server restarting.")

    def get_status(self) -> ServiceStatus:
        namespace = eg_settings.EG_NAMESPACE
        apps = get_k8s_client().apps()
        try:
            deploy = apps.read_namespaced_deployment(
                name="compassx-jupyter-server", namespace=namespace
            )
            available = deploy.status.available_replicas or 0
            if available >= 1:
                return ServiceStatus(phase=ServicePhase.RUNNING, message="Jupyter Server running.")
            return ServiceStatus(phase=ServicePhase.STARTING, message="Jupyter Server starting.")
        except ApiException as exc:
            if exc.status == 404:
                return ServiceStatus(phase=ServicePhase.STOPPED, message="Jupyter Server not deployed.")
            raise

    def get_resource_usage(self) -> ServiceResourceUsage:
        return ServiceResourceUsage(metrics_available=False)


_js_manager: JupyterServerManager | None = None


def get_js_manager() -> JupyterServerManager:
    global _js_manager
    if _js_manager is None:
        _js_manager = JupyterServerManager()
    return _js_manager
