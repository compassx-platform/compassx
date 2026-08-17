"""Builds K8s specs for the Enterprise Gateway Deployment and Service."""
from kubernetes import client

from services.enterprise_gateway.config import eg_settings
from services.enterprise_gateway.kernelspecs import RUNTIMES, configmap_key

_EG_SA = "compassx-eg"
_EG_ROLE = "compassx-eg-role"
_EG_ROLE_BINDING = "compassx-eg-rolebinding"


def build_eg_service_account(namespace: str) -> client.V1ServiceAccount:
    return client.V1ServiceAccount(
        api_version="v1",
        kind="ServiceAccount",
        metadata=client.V1ObjectMeta(name=_EG_SA, namespace=namespace),
    )


def build_eg_role(namespace: str) -> client.V1Role:
    """Role granting EG the minimum permissions it needs to manage kernels in pods."""
    return client.V1Role(
        api_version="rbac.authorization.k8s.io/v1",
        kind="Role",
        metadata=client.V1ObjectMeta(name=_EG_ROLE, namespace=namespace),
        rules=[
            # _get_pod: list pods by label selector
            # poll/kill/send_signal: get individual pod
            client.V1PolicyRule(
                api_groups=[""],
                resources=["pods"],
                verbs=["get", "list"],
            ),
            # _exec_in_pod: kubernetes stream exec
            client.V1PolicyRule(
                api_groups=[""],
                resources=["pods/exec"],
                verbs=["create", "get"],
            ),
        ],
    )


def build_eg_role_binding(namespace: str) -> client.V1RoleBinding:
    return client.V1RoleBinding(
        api_version="rbac.authorization.k8s.io/v1",
        kind="RoleBinding",
        metadata=client.V1ObjectMeta(name=_EG_ROLE_BINDING, namespace=namespace),
        subjects=[
            client.RbacV1Subject(
                kind="ServiceAccount",
                name=_EG_SA,
                namespace=namespace,
            )
        ],
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name=_EG_ROLE,
        ),
    )


def build_eg_deployment(namespace: str, env: str) -> client.V1Deployment:
    """EG Deployment spec.

    name: compassx-enterprise-gateway
    namespace: EG_NAMESPACE (compassx-services)
    """
    is_cloud = env != "local"
    image_pull_policy = "Always" if is_cloud else "IfNotPresent"

    resources = (
        client.V1ResourceRequirements(
            requests={"cpu": "150m", "memory": "256Mi"},
            limits={"cpu": "400m", "memory": "768Mi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "1", "memory": "1Gi"},
        )
    )

    env_vars = [
        client.V1EnvVar(
            name="EG_REMOTE_KERNEL_MANAGER_CLASS",
            value="enterprise_gateway.services.kernels.remotemanager.RemoteKernelManager",
        ),
        client.V1EnvVar(name="EG_NAMESPACE", value=eg_settings.KERNEL_NAMESPACE),
        client.V1EnvVar(name="KERNEL_NAMESPACE", value=eg_settings.KERNEL_NAMESPACE),
        client.V1EnvVar(name="EG_KERNEL_LAUNCH_TIMEOUT", value=str(eg_settings.EG_KERNEL_LAUNCH_TIMEOUT)),
        client.V1EnvVar(name="EG_PORT", value=str(eg_settings.EG_PORT)),
        client.V1EnvVar(name="EG_ALLOW_PASSWORD_CHANGE", value="false"),
        client.V1EnvVar(name="EG_PROCESS_PROXY_LAUNCH_TIMEOUT", value=str(eg_settings.EG_KERNEL_LAUNCH_TIMEOUT)),
        # Allow WebSocket connections from the browser dev server (any origin).
        # Without this EG rejects WS upgrades with a mismatched Origin header,
        # leaving the frontend kernel status stuck at 'unknown'.
        client.V1EnvVar(name="EG_ALLOW_ORIGIN", value="*"),
    ]

    container = client.V1Container(
        name="enterprise-gateway",
        image=eg_settings.EG_IMAGE,
        image_pull_policy=image_pull_policy,
        env=env_vars,
        ports=[client.V1ContainerPort(container_port=eg_settings.EG_PORT, name="eg")],
        resources=resources,
        volume_mounts=[
            # Each runtime gets its own subPath mount so the file lands at
            # /usr/local/share/jupyter/kernels/<runtime>_python/kernel.json
            client.V1VolumeMount(
                name="kernelspecs",
                mount_path=f"/usr/local/share/jupyter/kernels/{runtime}_python/kernel.json",
                sub_path=configmap_key(runtime),
                read_only=True,
            )
            for runtime in RUNTIMES
        ],
        liveness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(path="/api", port=eg_settings.EG_PORT),
            initial_delay_seconds=30,
            period_seconds=30,
        ),
    )

    labels = {
        "app": "compassx",
        "compassx/service": "enterprise-gateway",
    }

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name="compassx-enterprise-gateway",
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    service_account_name="compassx-eg",
                    containers=[container],
                    volumes=[
                        client.V1Volume(
                            name="kernelspecs",
                            config_map=client.V1ConfigMapVolumeSource(
                                name="compassx-kernelspecs"
                            ),
                        )
                    ],
                ),
            ),
        ),
    )


def build_eg_service(namespace: str) -> client.V1Service:
    """LoadBalancer service exposing EG on port 8888 for tunnel-based access."""
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name="compassx-enterprise-gateway",
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "enterprise-gateway"},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "compassx", "compassx/service": "enterprise-gateway"},
            ports=[
                client.V1ServicePort(
                    port=eg_settings.EG_PORT,
                    target_port=eg_settings.EG_PORT,
                    name="eg",
                )
            ],
            type="LoadBalancer",
        ),
    )




