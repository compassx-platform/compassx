"""Builds K8s specs for Jupyter Server Deployment and Service.

Jupyter Server connects to Enterprise Gateway for all kernel management.
It does NOT render notebook UI — that's the React app.
"""
from kubernetes import client

from services.enterprise_gateway.config import eg_settings


def build_jupyter_server_deployment(namespace: str, env: str) -> client.V1Deployment:
    """Jupyter Server Deployment spec.

    name: compassx-jupyter-server
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

    eg_url = (
        f"http://compassx-enterprise-gateway.{namespace}.svc.cluster.local"
        f":{eg_settings.EG_PORT}"
    )

    labels = {"app": "compassx", "compassx/service": "jupyter-server"}

    container = client.V1Container(
        name="jupyter-server",
        image=eg_settings.JUPYTER_SERVER_IMAGE,
        image_pull_policy=image_pull_policy,
        command=[
            "jupyter", "server",
            "--ServerApp.ip=0.0.0.0",
            f"--ServerApp.port={eg_settings.JUPYTER_SERVER_PORT}",
            "--ServerApp.token=",
            "--ServerApp.password=",
            "--ServerApp.allow_origin=*",
            f"--GatewayClient.url={eg_url}",
            "--GatewayClient.request_timeout=120",
            "--GatewayClient.connect_timeout=120",
        ],
        ports=[
            client.V1ContainerPort(container_port=eg_settings.JUPYTER_SERVER_PORT, name="jupyter")
        ],
        resources=resources,
    )

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name="compassx-jupyter-server",
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(containers=[container]),
            ),
        ),
    )


def build_jupyter_server_service(namespace: str, env: str) -> client.V1Service:
    """Service for Jupyter Server.

    LoadBalancer for minikube tunnel or cloud ingress exposure.
    """
    port = client.V1ServicePort(
        port=eg_settings.JUPYTER_SERVER_PORT,
        target_port=eg_settings.JUPYTER_SERVER_PORT,
        name="jupyter",
    )
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name="compassx-jupyter-server",
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "jupyter-server"},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "compassx", "compassx/service": "jupyter-server"},
            ports=[port],
            type="LoadBalancer",
        ),
    )




