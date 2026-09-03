"""Backend runtime helpers.

This module controls the optional backend-in-pod mode used for pod-based testing.
When enabled, the host process can provision/refresh the backend Deployment and
Service so the app can be exercised through cluster DNS instead of port-forward.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from time import monotonic, sleep

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from compute.config import compute_settings
from compute.k8s_client import get_k8s_client

logger = logging.getLogger(__name__)

BACKEND_DEPLOYMENT_NAME = "compassx-backend"
BACKEND_SERVICE_NAME = "compassx-backend"
BACKEND_NAMESPACE = compute_settings.COMPASSX_NAMESPACE
BACKEND_PORT = 8000
BACKEND_LOCAL_PORT = 18080
BACKEND_IMAGE = "compassx-backend:latest"
BACKEND_SERVICE_ACCOUNT = "compassx-backend"
BACKEND_CONFIG_MAP = "compassx-app-config"
BACKEND_SECRET = "compassx-backend-secrets"
BACKEND_RUNTIME_TIMEOUT_SECONDS = 120
BACKEND_FORWARD_READY_FILE = "/tmp/compassx-backend-port-forward.ready"


@dataclass(frozen=True)
class BackendRuntimeInfo:
    mode: str
    namespace: str
    deployment_name: str
    service_name: str
    service_url: str
    ready: bool


def is_pod_runtime() -> bool:
    return compute_settings.backend_runtime_is_pod()


def running_in_cluster() -> bool:
    return bool(os.environ.get("KUBERNETES_SERVICE_HOST"))


def backend_service_url(namespace: str | None = None) -> str:
    ns = namespace or BACKEND_NAMESPACE
    if is_pod_runtime():
        if running_in_cluster():
            return f"http://{BACKEND_SERVICE_NAME}.{ns}.svc.cluster.local:{BACKEND_PORT}"
        return f"http://127.0.0.1:{BACKEND_LOCAL_PORT}"
    return "http://127.0.0.1:8000"


def backend_catalog_url(namespace: str | None = None) -> str:
    return f"{backend_service_url(namespace)}/api/v1/catalog"


def get_runtime_info(ready: bool | None = None) -> BackendRuntimeInfo:
    if ready is None:
        ready = _backend_is_ready(BACKEND_NAMESPACE) if is_pod_runtime() else True
    return BackendRuntimeInfo(
        mode="pod" if is_pod_runtime() else "host",
        namespace=BACKEND_NAMESPACE,
        deployment_name=BACKEND_DEPLOYMENT_NAME,
        service_name=BACKEND_SERVICE_NAME,
        service_url=backend_service_url(),
        ready=ready,
    )


def _ensure_namespace(name: str) -> None:
    k8s = get_k8s_client()
    try:
        k8s.core().read_namespace(name=name)
    except ApiException as exc:
        if exc.status == 404:
            k8s.core().create_namespace(
                body=client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            )
        else:
            raise


def _backend_env_items() -> list[client.V1EnvVar]:
    backend_runtime = compute_settings.resolved_backend_runtime()
    return [
        client.V1EnvVar(name="COMPASSX_ENV", value=compute_settings.COMPASSX_ENV),
        client.V1EnvVar(name="COMPASSX_BACKEND_RUNTIME", value=backend_runtime),
        client.V1EnvVar(name="CATALOG_API_URL", value=backend_catalog_url()),
        client.V1EnvVar(name="LOCAL_K8S_BOOTSTRAP_ENABLED", value=str(compute_settings.LOCAL_K8S_BOOTSTRAP_ENABLED).lower()),
        client.V1EnvVar(name="SKIP_K8S_SSL_VERIFY", value=str(compute_settings.SKIP_K8S_SSL_VERIFY).lower()),
    ]


def build_backend_service_account(namespace: str) -> client.V1ServiceAccount:
    return client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name=BACKEND_SERVICE_ACCOUNT,
            namespace=namespace,
            labels={"app": BACKEND_DEPLOYMENT_NAME},
        )
    )


def build_backend_role(namespace: str) -> client.V1Role:
    return client.V1Role(
        metadata=client.V1ObjectMeta(name=BACKEND_SERVICE_ACCOUNT, namespace=namespace),
        rules=[
            client.V1PolicyRule(api_groups=[""], resources=["pods", "services", "configmaps"], verbs=["get", "list", "watch"]),
            client.V1PolicyRule(api_groups=[""], resources=["pods/exec"], verbs=["create", "get"]),
        ],
    )


def build_backend_role_binding(namespace: str) -> client.V1RoleBinding:
    return client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name=BACKEND_SERVICE_ACCOUNT, namespace=namespace),
        subjects=[client.V1Subject(kind="ServiceAccount", name=BACKEND_SERVICE_ACCOUNT, namespace=namespace)],
        role_ref=client.V1RoleRef(api_group="rbac.authorization.k8s.io", kind="Role", name=BACKEND_SERVICE_ACCOUNT),
    )


def build_backend_deployment(namespace: str) -> client.V1Deployment:
    labels = {"app": BACKEND_DEPLOYMENT_NAME}
    return client.V1Deployment(
        metadata=client.V1ObjectMeta(name=BACKEND_DEPLOYMENT_NAME, namespace=namespace, labels=labels),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    service_account_name=BACKEND_SERVICE_ACCOUNT,
                    containers=[
                        client.V1Container(
                            name="backend",
                            image=BACKEND_IMAGE,
                            image_pull_policy="IfNotPresent",
                            args=["python", "app.py"],
                            working_dir="/ms-home",
                            ports=[client.V1ContainerPort(container_port=BACKEND_PORT, name="http")],
                            env=_backend_env_items(),
                            env_from=[
                                client.V1EnvFromSource(config_map_ref=client.V1ConfigMapEnvSource(name=BACKEND_CONFIG_MAP)),
                                client.V1EnvFromSource(secret_ref=client.V1SecretEnvSource(name=BACKEND_SECRET)),
                            ],
                            readiness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(path="/healthcheck", port="http"),
                                initial_delay_seconds=10,
                                period_seconds=5,
                            ),
                            liveness_probe=client.V1Probe(
                                http_get=client.V1HTTPGetAction(path="/healthcheck", port="http"),
                                initial_delay_seconds=20,
                                period_seconds=20,
                            ),
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": "150m", "memory": "256Mi"},
                                limits={"cpu": "500m", "memory": "512Mi"},
                            ),
                        )
                    ],
                ),
            ),
        ),
    )


def build_backend_service(namespace: str) -> client.V1Service:
    return client.V1Service(
        metadata=client.V1ObjectMeta(name=BACKEND_SERVICE_NAME, namespace=namespace),
        spec=client.V1ServiceSpec(
            selector={"app": BACKEND_DEPLOYMENT_NAME},
            ports=[client.V1ServicePort(port=BACKEND_PORT, target_port=BACKEND_PORT, name="http")],
            type="ClusterIP",
        ),
    )


def _create_or_replace_core(core, create_fn_name: str, replace_fn_name: str, name: str, namespace: str, body) -> None:
    try:
        getattr(core, replace_fn_name)(name=name, namespace=namespace, body=body)
    except ApiException as exc:
        if exc.status == 404:
            getattr(core, create_fn_name)(namespace=namespace, body=body)
        else:
            raise


def _create_or_replace_apps(apps, name: str, namespace: str, body) -> None:
    try:
        apps.replace_namespaced_deployment(name=name, namespace=namespace, body=body)
    except ApiException as exc:
        if exc.status == 404:
            apps.create_namespaced_deployment(namespace=namespace, body=body)
        else:
            raise


def _backend_is_ready(namespace: str) -> bool:
    if not is_pod_runtime():
        return True
    try:
        k8s = get_k8s_client()
        deploy = k8s.apps().read_namespaced_deployment(name=BACKEND_DEPLOYMENT_NAME, namespace=namespace)
        if (deploy.status.available_replicas or 0) < 1:
            return False
        svc = k8s.core().read_namespaced_service(name=BACKEND_SERVICE_NAME, namespace=namespace)
        return svc is not None
    except Exception:
        return False


def mark_backend_port_forward_ready() -> None:
    try:
        with open(BACKEND_FORWARD_READY_FILE, "w", encoding="utf-8") as fh:
            fh.write("ready\n")
    except OSError:
        pass


def clear_backend_port_forward_ready() -> None:
    try:
        os.remove(BACKEND_FORWARD_READY_FILE)
    except OSError:
        pass


def backend_port_forward_ready() -> bool:
    return os.path.exists(BACKEND_FORWARD_READY_FILE)


class BackendRuntimeManager:
    def ensure_backend_pod(self) -> None:
        if not is_pod_runtime():
            return

        namespace = BACKEND_NAMESPACE
        _ensure_namespace(namespace)
        k8s = get_k8s_client()
        apps = k8s.apps()
        core = k8s.core()

        service_account = build_backend_service_account(namespace)
        role = build_backend_role(namespace)
        role_binding = build_backend_role_binding(namespace)
        _create_or_replace_core(core, "create_namespaced_service_account", "replace_namespaced_service_account", service_account.metadata.name, namespace, service_account)
        try:
            k8s.rbac().replace_namespaced_role(name=role.metadata.name, namespace=namespace, body=role)
        except ApiException as exc:
            if exc.status == 404:
                k8s.rbac().create_namespaced_role(namespace=namespace, body=role)
            else:
                raise
        try:
            k8s.rbac().replace_namespaced_role_binding(name=role_binding.metadata.name, namespace=namespace, body=role_binding)
        except ApiException as exc:
            if exc.status == 404:
                k8s.rbac().create_namespaced_role_binding(namespace=namespace, body=role_binding)
            else:
                raise

        deployment = build_backend_deployment(namespace)
        service = build_backend_service(namespace)

        _create_or_replace_apps(apps, deployment.metadata.name, namespace, deployment)
        _create_or_replace_core(core, "create_namespaced_service", "replace_namespaced_service", service.metadata.name, namespace, service)
        logger.info("backend-runtime: backend workload reconciled in namespace %s", namespace)

    def wait_until_ready(self, timeout_seconds: int = BACKEND_RUNTIME_TIMEOUT_SECONDS) -> bool:
        if not is_pod_runtime():
            return True

        deadline = monotonic() + timeout_seconds
        while monotonic() < deadline:
            if _backend_is_ready(BACKEND_NAMESPACE):
                return True
            sleep(2)
        return False

    def backend_port_forward_required(self) -> bool:
        return is_pod_runtime() and not running_in_cluster()


_backend_runtime_manager: BackendRuntimeManager | None = None


def get_backend_runtime_manager() -> BackendRuntimeManager:
    global _backend_runtime_manager
    if _backend_runtime_manager is None:
        _backend_runtime_manager = BackendRuntimeManager()
    return _backend_runtime_manager
