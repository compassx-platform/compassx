"""ComputeManager for lifecycle of deployments backing compute resources."""
import logging
from datetime import datetime, timezone

from kubernetes import client as k8s_client
from kubernetes.client.exceptions import ApiException

from compute.config import compute_settings
from compute.k8s_client import get_k8s_client
from compute.runtimes import build_deployment_spec
from compute.schemas import JobResponse, JobStatus

logger = logging.getLogger(__name__)


class JobNotFoundError(Exception):
    """Raised when a resource deployment or its pod cannot be resolved."""


class ComputeManager:
    """Manages deployment-backed all-purpose compute resources via Kubernetes."""

    def _ensure_namespace(self, namespace: str) -> None:
        k8s = get_k8s_client()
        try:
            k8s.core().read_namespace(name=namespace)
            logger.debug("K8s: namespace %s exists", namespace)
        except ApiException as exc:
            if exc.status != 404:
                raise
            ns = k8s_client.V1Namespace(
                metadata=k8s_client.V1ObjectMeta(
                    name=namespace,
                    labels={"compassx/managed": "true"},
                )
            )
            k8s.core().create_namespace(body=ns)
            logger.info("K8s: namespace %s created", namespace)

    def create_resource_job(
        self,
        resource_id: str,
        resource_name: str,
        runtime: str,
        profile,
        user_id: str,
        custom_image: str | None = None,
        extra_env: dict | None = None,
        deployment_name: str | None = None,
    ) -> JobResponse:
        """Create or restart a deployment for a compute resource."""
        namespace = compute_settings.COMPASSX_NAMESPACE
        env = compute_settings.COMPASSX_ENV
        deployment_name = deployment_name or f"compassx-compute-{resource_id}"

        deployment = build_deployment_spec(
            deployment_name=deployment_name,
            resource_id=resource_id,
            user_id=user_id,
            runtime=runtime,
            profile=profile,
            namespace=namespace,
            env=env,
            custom_image=custom_image,
            extra_env=extra_env,
            replicas=1,
        )

        k8s = get_k8s_client()
        self._ensure_namespace(namespace)
        apps = k8s.apps()
        now = datetime.now(timezone.utc)

        try:
            existing = apps.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        except ApiException as exc:
            if exc.status != 404:
                raise
            apps.create_namespaced_deployment(namespace=namespace, body=deployment)
            logger.info(
                "Deployment created for resource: resource_id=%s deployment=%s runtime=%s",
                resource_id,
                deployment_name,
                runtime,
            )
        else:
            deployment.metadata.resource_version = existing.metadata.resource_version
            apps.replace_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
            logger.info(
                "Deployment updated for resource: resource_id=%s deployment=%s runtime=%s",
                resource_id,
                deployment_name,
                runtime,
            )

        pod = self.get_pod_for_resource(resource_id)
        pod_name = pod.metadata.name if pod and pod.metadata else None
        return JobResponse(
            job_id=resource_id,
            pod_name=pod_name or deployment_name,
            namespace=namespace,
            runtime=runtime,
            profile=profile.id,
            status="Pending",
            created_at=now,
        )

    def get_pod_for_resource(self, resource_id: str):
        """Return the newest pod for a resource, preferring Running pods."""
        k8s = get_k8s_client()
        pods = k8s.core().list_namespaced_pod(
            namespace=compute_settings.COMPASSX_NAMESPACE,
            label_selector=f"compassx/resource={resource_id}",
        )
        if not pods.items:
            return None
        items = sorted(
            pods.items,
            key=lambda pod: (
                0 if (pod.status and pod.status.phase == "Running") else 1,
                pod.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        return items[0]

    def get_job_status(
        self,
        job_id: str,
        *,
        runtime: str | None = None,
        profile: str | None = None,
        user_id: str | None = None,
        created_at=None,
    ) -> JobStatus:
        """Resolve live status for a deployment-backed resource."""
        pod = self.get_pod_for_resource(job_id)
        if pod is None:
            raise JobNotFoundError(f"No pod found for resource: {job_id}")

        phase = pod.status.phase if pod.status and pod.status.phase else "Unknown"
        started_at = pod.status.start_time if pod.status else None
        finished_at = None
        message = None

        if pod.status:
            for container_status in pod.status.container_statuses or []:
                if container_status.state and container_status.state.terminated:
                    terminated = container_status.state.terminated
                    finished_at = terminated.finished_at
                    if terminated.reason == "OOMKilled":
                        message = "Out of memory. Try a larger compute profile."
                        phase = "Failed"
                    elif terminated.reason in ("ErrImagePull", "ImagePullBackOff"):
                        message = "Image could not be pulled. Check runtime image."
                        phase = "Failed"
                    elif terminated.exit_code and terminated.exit_code != 0:
                        message = terminated.message or f"Container exited with code {terminated.exit_code}"

        labels = pod.metadata.labels or {}
        annotations = pod.metadata.annotations or {}
        return JobStatus(
            job_id=job_id,
            pod_name=pod.metadata.name,
            phase=phase,
            runtime=runtime or labels.get("runtime", "unknown"),
            profile=profile or annotations.get("compassx/profile", "unknown"),
            user_id=user_id or labels.get("user", "unknown"),
            created_at=created_at or pod.metadata.creation_timestamp or datetime.now(timezone.utc),
            started_at=started_at,
            finished_at=finished_at,
            message=message,
        )

    def stop_resource_job(self, deployment_name: str) -> bool:
        """Scale a resource deployment to zero replicas."""
        apps = get_k8s_client().apps()
        namespace = compute_settings.COMPASSX_NAMESPACE
        try:
            apps.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=namespace,
                body={"spec": {"replicas": 0}},
            )
            logger.info("Deployment scaled to zero: %s", deployment_name)
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            raise

    def delete_resource_job(self, deployment_name: str) -> bool:
        """Delete a resource deployment entirely."""
        apps = get_k8s_client().apps()
        namespace = compute_settings.COMPASSX_NAMESPACE
        try:
            apps.delete_namespaced_deployment(name=deployment_name, namespace=namespace)
            logger.info("Deployment deleted: %s", deployment_name)
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            raise

    def get_deployment_status(self, deployment_name: str) -> tuple[bool, int]:
        """Return whether a deployment exists and its desired replica count."""
        apps = get_k8s_client().apps()
        namespace = compute_settings.COMPASSX_NAMESPACE
        try:
            deployment = apps.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        except ApiException as exc:
            if exc.status == 404:
                return False, 0
            raise
        return True, deployment.spec.replicas or 0

    def cleanup_completed_jobs(self) -> None:
        """No-op for deployment-backed compute resources."""
        logger.debug("cleanup_completed_jobs: skipped for deployment-backed compute resources")


_manager: ComputeManager | None = None


def get_compute_manager() -> ComputeManager:
    """Return the singleton ComputeManager."""
    global _manager
    if _manager is None:
        _manager = ComputeManager()
    return _manager
