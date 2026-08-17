"""Airflow service manager - start/stop/restart/status."""
import logging
import time
from datetime import datetime, timezone

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from compute.config import compute_settings
from compute.k8s_client import get_k8s_client
from services.airflow.config import airflow_settings
from services.airflow.manifests import (
    build_airflow_dags_pvc,
    build_airflow_init_job,
    build_airflow_logs_pvc,
    build_airflow_redis_deployment,
    build_airflow_redis_service,
    build_airflow_role,
    build_airflow_role_binding,
    build_airflow_scheduler_deployment,
    build_airflow_service,
    build_airflow_service_account,
    build_airflow_webserver_deployment,
    build_airflow_worker_deployment,
)
from services.base import BaseServiceManager, ServicePhase, ServiceResourceUsage, ServiceStatus

logger = logging.getLogger(__name__)


class AirflowManager(BaseServiceManager):
    """Manages the Airflow K8s Deployment."""

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

    def _run_init_job(self, namespace: str, env: str) -> None:
        batch = get_k8s_client().batch()
        job_name = airflow_settings.AIRFLOW_INIT_JOB_NAME
        job = build_airflow_init_job(namespace, env)

        try:
            batch.delete_namespaced_job(
                name=job_name,
                namespace=namespace,
                propagation_policy="Background",
            )
        except ApiException as exc:
            if exc.status != 404:
                raise

        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                get_k8s_client().core().delete_collection_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"job-name={job_name}",
                )
                break
            except ApiException:
                time.sleep(1)

        batch.create_namespaced_job(namespace=namespace, body=job)
        logger.info("start: created Airflow init job")

        logger.info("start: Airflow init job submitted; continuing startup without waiting")

    def start(self) -> ServiceStatus:
        namespace = airflow_settings.AIRFLOW_NAMESPACE
        env = compute_settings.COMPASSX_ENV
        self._ensure_namespace(namespace)

        k8s = get_k8s_client()
        apps = k8s.apps()
        rbac = k8s.rbac()
        core = k8s.core()
        dags_pvc = build_airflow_dags_pvc(namespace)
        logs_pvc = build_airflow_logs_pvc(namespace)

        service_account = build_airflow_service_account(namespace)
        role = build_airflow_role(namespace)
        role_binding = build_airflow_role_binding(namespace)

        try:
            core.replace_namespaced_service_account(
                name=airflow_settings.AIRFLOW_SERVICE_ACCOUNT_NAME,
                namespace=namespace,
                body=service_account,
            )
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespaced_service_account(namespace=namespace, body=service_account)
            else:
                raise

        try:
            rbac.replace_namespaced_role(
                name=role.metadata.name,
                namespace=namespace,
                body=role,
            )
        except ApiException as exc:
            if exc.status == 404:
                rbac.create_namespaced_role(namespace=namespace, body=role)
            else:
                raise

        try:
            rbac.replace_namespaced_role_binding(
                name=role_binding.metadata.name,
                namespace=namespace,
                body=role_binding,
            )
        except ApiException as exc:
            if exc.status == 404:
                rbac.create_namespaced_role_binding(namespace=namespace, body=role_binding)
            else:
                raise

        try:
            core.read_namespaced_persistent_volume_claim(
                name=airflow_settings.AIRFLOW_DAGS_PVC_NAME,
                namespace=namespace,
            )
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespaced_persistent_volume_claim(namespace=namespace, body=dags_pvc)
            else:
                raise

        try:
            core.read_namespaced_persistent_volume_claim(
                name=airflow_settings.AIRFLOW_LOGS_PVC_NAME,
                namespace=namespace,
            )
        except ApiException as exc:
            if exc.status == 404:
                core.create_namespaced_persistent_volume_claim(namespace=namespace, body=logs_pvc)
            else:
                raise

        self._run_init_job(namespace, env)

        deployments = [
            build_airflow_redis_deployment(namespace, env),
            build_airflow_scheduler_deployment(namespace, env),
            build_airflow_worker_deployment(namespace, env),
            build_airflow_webserver_deployment(namespace, env),
        ]
        for deployment in deployments:
            try:
                apps.replace_namespaced_deployment(
                    name=deployment.metadata.name,
                    namespace=namespace,
                    body=deployment,
                )
                logger.info("start: replaced Airflow deployment %s", deployment.metadata.name)
            except ApiException as exc:
                if exc.status == 404:
                    apps.create_namespaced_deployment(namespace=namespace, body=deployment)
                    logger.info("start: created Airflow deployment %s", deployment.metadata.name)
                else:
                    raise

        services = [
            build_airflow_service(namespace, env),
            build_airflow_redis_service(namespace),
        ]
        for service in services:
            try:
                core.replace_namespaced_service(
                    name=service.metadata.name,
                    namespace=namespace,
                    body=service,
                )
            except ApiException as exc:
                if exc.status == 404:
                    core.create_namespaced_service(namespace=namespace, body=service)
                else:
                    raise

        return ServiceStatus(
            phase=ServicePhase.STARTING,
            message="Airflow starting.",
            details=self._details(),
        )

    def stop(self) -> ServiceStatus:
        namespace = airflow_settings.AIRFLOW_NAMESPACE
        apps = get_k8s_client().apps()
        core = get_k8s_client().core()

        for delete_fn, name in [
            (apps.delete_namespaced_deployment, airflow_settings.AIRFLOW_WEBSERVER_DEPLOYMENT_NAME),
            (apps.delete_namespaced_deployment, airflow_settings.AIRFLOW_SCHEDULER_DEPLOYMENT_NAME),
            (apps.delete_namespaced_deployment, airflow_settings.AIRFLOW_WORKER_DEPLOYMENT_NAME),
            (apps.delete_namespaced_deployment, airflow_settings.AIRFLOW_REDIS_DEPLOYMENT_NAME),
            (core.delete_namespaced_service, airflow_settings.AIRFLOW_SERVICE_NAME),
            (core.delete_namespaced_service, airflow_settings.AIRFLOW_REDIS_SERVICE_NAME),
            (core.delete_namespaced_service_account, airflow_settings.AIRFLOW_SERVICE_ACCOUNT_NAME),
        ]:
            try:
                delete_fn(name=name, namespace=namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise

        batch = get_k8s_client().batch()
        try:
            batch.delete_namespaced_job(
                name=airflow_settings.AIRFLOW_INIT_JOB_NAME,
                namespace=namespace,
                propagation_policy="Background",
            )
        except ApiException as exc:
            if exc.status != 404:
                raise

        rbac = get_k8s_client().rbac()
        for delete_fn, name in [
            (rbac.delete_namespaced_role_binding, "compassx-airflow-rolebinding"),
            (rbac.delete_namespaced_role, "compassx-airflow-role"),
        ]:
            try:
                delete_fn(name=name, namespace=namespace)
            except ApiException as exc:
                if exc.status != 404:
                    raise

        return ServiceStatus(
            phase=ServicePhase.STOPPED,
            message="Airflow stopped.",
            details=self._details(),
        )

    def restart(self) -> ServiceStatus:
        namespace = airflow_settings.AIRFLOW_NAMESPACE
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
        apps = get_k8s_client().apps()
        for deployment_name in [
            airflow_settings.AIRFLOW_WEBSERVER_DEPLOYMENT_NAME,
            airflow_settings.AIRFLOW_SCHEDULER_DEPLOYMENT_NAME,
            airflow_settings.AIRFLOW_WORKER_DEPLOYMENT_NAME,
            airflow_settings.AIRFLOW_REDIS_DEPLOYMENT_NAME,
        ]:
            apps.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch,
            )
        return ServiceStatus(
            phase=ServicePhase.STARTING,
            message="Airflow restarting.",
            details=self._details(),
        )

    def get_status(self) -> ServiceStatus:
        namespace = airflow_settings.AIRFLOW_NAMESPACE
        apps = get_k8s_client().apps()
        try:
            web = apps.read_namespaced_deployment(
                name=airflow_settings.AIRFLOW_WEBSERVER_DEPLOYMENT_NAME,
                namespace=namespace,
            )
            scheduler = apps.read_namespaced_deployment(
                name=airflow_settings.AIRFLOW_SCHEDULER_DEPLOYMENT_NAME,
                namespace=namespace,
            )
            worker = apps.read_namespaced_deployment(
                name=airflow_settings.AIRFLOW_WORKER_DEPLOYMENT_NAME,
                namespace=namespace,
            )
            redis = apps.read_namespaced_deployment(
                name=airflow_settings.AIRFLOW_REDIS_DEPLOYMENT_NAME,
                namespace=namespace,
            )
            if all((deploy.status.available_replicas or 0) >= 1 for deploy in [web, scheduler, worker, redis]):
                return ServiceStatus(
                    phase=ServicePhase.RUNNING,
                    message="Airflow running.",
                    details=self._details(),
                )
            return ServiceStatus(
                phase=ServicePhase.STARTING,
                message="Airflow starting.",
                details=self._details(),
            )
        except ApiException as exc:
            if exc.status == 404:
                return ServiceStatus(
                    phase=ServicePhase.STOPPED,
                    message="Airflow not deployed.",
                    details=self._details(),
                )
            raise

    def get_resource_usage(self) -> ServiceResourceUsage:
        return ServiceResourceUsage(metrics_available=False)

    def _details(self) -> dict:
        return {
            "namespace": airflow_settings.AIRFLOW_NAMESPACE,
            "service_name": airflow_settings.AIRFLOW_SERVICE_NAME,
            "port": airflow_settings.AIRFLOW_PORT,
            "ui_url": airflow_settings.ui_url(),
        }


_airflow_manager: AirflowManager | None = None


def get_airflow_manager() -> AirflowManager:
    global _airflow_manager
    if _airflow_manager is None:
        _airflow_manager = AirflowManager()
    return _airflow_manager
