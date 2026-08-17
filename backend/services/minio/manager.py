"""MinIO service manager."""
import logging

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from compute.config import compute_settings
from compute.k8s_client import get_k8s_client
from services.base import BaseServiceManager, ServicePhase, ServiceResourceUsage, ServiceStatus
from services.enterprise_gateway.config import eg_settings
from services.minio.config import minio_settings
from services.minio.manifests import (
    bucket_names,
    build_minio_console_service,
    build_minio_deployment,
    build_minio_pvc,
    build_minio_service,
)
from services.storage.config import storage_settings
from services.storage.fs import MinioFS

logger = logging.getLogger(__name__)


class MinioManager(BaseServiceManager):
    def _ensure_namespace(self, namespace: str) -> None:
        core = get_k8s_client().core()
        try:
            core.read_namespace(name=namespace)
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespace(
                    body=client.V1Namespace(
                        metadata=client.V1ObjectMeta(
                            name=namespace,
                            labels={"compassx/managed": "true"},
                        )
                    )
                )
            else:
                raise

    def start(self) -> ServiceStatus:
        namespace = minio_settings.MINIO_NAMESPACE
        self._ensure_namespace(namespace)
        core = get_k8s_client().core()
        apps = get_k8s_client().apps()

        pvc = build_minio_pvc(namespace)
        try:
            core.read_namespaced_persistent_volume_claim(
                name=minio_settings.MINIO_PVC_NAME,
                namespace=namespace,
            )
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)
            else:
                raise

        deployment = build_minio_deployment(namespace)
        try:
            apps.replace_namespaced_deployment(
                name=minio_settings.MINIO_DEPLOYMENT_NAME,
                namespace=namespace,
                body=deployment,
            )
        except ApiException as exc:
            if exc.status == 404:
                apps.create_namespaced_deployment(namespace=namespace, body=deployment)
            else:
                raise

        for svc in [build_minio_service(namespace), build_minio_console_service(namespace)]:
            try:
                core.replace_namespaced_service(
                    name=svc.metadata.name,
                    namespace=namespace,
                    body=svc,
                )
            except ApiException as exc:
                if exc.status == 404:
                    core.create_namespaced_service(namespace=namespace, body=svc)
                else:
                    raise

        return ServiceStatus(phase=ServicePhase.STARTING, message="MinIO starting.", details=self._details())

    def stop(self) -> ServiceStatus:
        namespace = minio_settings.MINIO_NAMESPACE
        core = get_k8s_client().core()
        apps = get_k8s_client().apps()
        for delete_fn, name in [
            (apps.delete_namespaced_deployment, minio_settings.MINIO_DEPLOYMENT_NAME),
            (core.delete_namespaced_service, minio_settings.MINIO_SERVICE_NAME),
            (core.delete_namespaced_service, minio_settings.MINIO_CONSOLE_SERVICE_NAME),
        ]:
            try:
                delete_fn(name=name, namespace=namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise
        return ServiceStatus(phase=ServicePhase.STOPPED, message="MinIO stopped.", details=self._details())

    def restart(self) -> ServiceStatus:
        return self.start()

    def get_status(self) -> ServiceStatus:
        apps = get_k8s_client().apps()
        namespace = minio_settings.MINIO_NAMESPACE
        try:
            deploy = apps.read_namespaced_deployment(
                name=minio_settings.MINIO_DEPLOYMENT_NAME,
                namespace=namespace,
            )
            available = deploy.status.available_replicas or 0
            phase = ServicePhase.RUNNING if available >= 1 else ServicePhase.STARTING
            msg = "MinIO running." if available >= 1 else "MinIO starting."
            return ServiceStatus(phase=phase, message=msg, details=self._details())
        except ApiException as exc:
            if exc.status == 404:
                return ServiceStatus(phase=ServicePhase.STOPPED, message="MinIO not deployed.", details=self._details())
            raise

    def get_resource_usage(self) -> ServiceResourceUsage:
        return ServiceResourceUsage(metrics_available=False)

    def ensure_buckets(self) -> None:
        fs = MinioFS()
        for bucket in bucket_names():
            fs.ensure_bucket(bucket)
        logger.info("minio: buckets ready: %s", ", ".join(bucket_names()))

    def _details(self) -> dict:
        external_ui_url = minio_settings.MINIO_CONSOLE_EXTERNAL_URL.strip()
        return {
            "namespace": minio_settings.MINIO_NAMESPACE,
            "service_name": minio_settings.MINIO_SERVICE_NAME,
            "console_service_name": minio_settings.MINIO_CONSOLE_SERVICE_NAME,
            "endpoint": storage_settings.minio_endpoint_for_app(),
            "ui_url": (
                f"http://localhost:{minio_settings.MINIO_CONSOLE_PORT}"
                if compute_settings.is_local()
                else (
                    external_ui_url
                    or f"http://{minio_settings.MINIO_CONSOLE_SERVICE_NAME}.{eg_settings.EG_NAMESPACE}.svc.cluster.local:{minio_settings.MINIO_CONSOLE_PORT}"
                )
            ),
            "dags_bucket": storage_settings.STORAGE_DAGS_BUCKET,
            "outputs_bucket": storage_settings.STORAGE_OUTPUTS_BUCKET,
        }


_minio_manager: MinioManager | None = None


def get_minio_manager() -> MinioManager:
    global _minio_manager
    if _minio_manager is None:
        _minio_manager = MinioManager()
    return _minio_manager
