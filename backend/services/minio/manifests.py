"""K8s manifests for the MinIO service."""
from kubernetes import client

from compute.config import compute_settings
from services.minio.config import minio_settings
from services.storage.config import storage_settings


def build_minio_pvc(namespace: str) -> client.V1PersistentVolumeClaim:
    return client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=client.V1ObjectMeta(name=minio_settings.MINIO_PVC_NAME, namespace=namespace),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1VolumeResourceRequirements(
                requests={"storage": minio_settings.MINIO_STORAGE_SIZE}
            ),
        ),
    )


def build_minio_deployment(namespace: str) -> client.V1Deployment:
    labels = {"app": "compassx", "compassx/service": "minio"}
    minio_server_url = (
        f"http://localhost:{minio_settings.MINIO_PORT}"
        if compute_settings.is_local()
        else f"http://{minio_settings.MINIO_SERVICE_NAME}.{namespace}.svc.cluster.local:{minio_settings.MINIO_PORT}"
    )
    minio_console_url = (
        f"http://localhost:{minio_settings.MINIO_CONSOLE_PORT}"
        if compute_settings.is_local()
        else f"http://{minio_settings.MINIO_CONSOLE_SERVICE_NAME}.{namespace}.svc.cluster.local:{minio_settings.MINIO_CONSOLE_PORT}"
    )
    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=minio_settings.MINIO_DEPLOYMENT_NAME,
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="minio",
                            image=minio_settings.MINIO_IMAGE,
                            args=[
                                "server",
                                "/data",
                                "--console-address",
                                f":{minio_settings.MINIO_CONSOLE_PORT}",
                            ],
                            env=[
                                client.V1EnvVar(
                                    name="MINIO_ROOT_USER",
                                    value=minio_settings.MINIO_ROOT_USER,
                                ),
                                client.V1EnvVar(
                                    name="MINIO_ROOT_PASSWORD",
                                    value=minio_settings.MINIO_ROOT_PASSWORD,
                                ),
                                # Required for login redirects to work via kubectl port-forward.
                                # Without these, MinIO console redirects to the internal cluster
                                # address after login, which is unreachable from the browser.
                                client.V1EnvVar(
                                    name="MINIO_SERVER_URL",
                                    value=minio_server_url,
                                ),
                                client.V1EnvVar(
                                    name="MINIO_BROWSER_REDIRECT_URL",
                                    value=minio_console_url,
                                ),
                            ],
                            ports=[
                                client.V1ContainerPort(container_port=minio_settings.MINIO_PORT, name="api"),
                                client.V1ContainerPort(container_port=minio_settings.MINIO_CONSOLE_PORT, name="console"),
                            ],
                            volume_mounts=[client.V1VolumeMount(name="minio-data", mount_path="/data")],
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": "250m", "memory": "512Mi"},
                                limits={"cpu": "1", "memory": "1Gi"},
                            ),
                        )
                    ],
                    volumes=[
                        client.V1Volume(
                            name="minio-data",
                            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=minio_settings.MINIO_PVC_NAME
                            ),
                        )
                    ],
                ),
            ),
        ),
    )


def build_minio_service(namespace: str) -> client.V1Service:
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=minio_settings.MINIO_SERVICE_NAME,
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "minio"},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "compassx", "compassx/service": "minio"},
            ports=[client.V1ServicePort(name="api", port=minio_settings.MINIO_PORT, target_port=minio_settings.MINIO_PORT)],
        ),
    )


def build_minio_console_service(namespace: str) -> client.V1Service:
    service_type = minio_settings.MINIO_CONSOLE_SERVICE_TYPE or "ClusterIP"
    service_port = client.V1ServicePort(
        name="console",
        port=minio_settings.MINIO_CONSOLE_PORT,
        target_port=minio_settings.MINIO_CONSOLE_PORT,
    )
    if minio_settings.MINIO_CONSOLE_NODE_PORT:
        service_port.node_port = minio_settings.MINIO_CONSOLE_NODE_PORT

    spec = client.V1ServiceSpec(
        type=service_type,
        selector={"app": "compassx", "compassx/service": "minio"},
        ports=[service_port],
    )
    if minio_settings.MINIO_CONSOLE_LOAD_BALANCER_IP:
        spec.load_balancer_ip = minio_settings.MINIO_CONSOLE_LOAD_BALANCER_IP

    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=minio_settings.MINIO_CONSOLE_SERVICE_NAME,
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "minio-console"},
        ),
        spec=spec,
    )


def bucket_names() -> list[str]:
    return [
        storage_settings.STORAGE_DAGS_BUCKET,
        storage_settings.STORAGE_OUTPUTS_BUCKET,
        storage_settings.STORAGE_NOTEBOOKS_BUCKET,
    ]
