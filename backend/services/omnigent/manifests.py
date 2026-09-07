"""Kubernetes manifests builder for Databricks Omnigent Server."""
from kubernetes import client

from app.config import settings
from services.omnigent.config import omnigent_settings


def build_omnigent_pvc(namespace: str) -> client.V1PersistentVolumeClaim:
    """PVC for Omnigent Server persistent storage (artifacts, telemetry, cached data)."""
    return client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=client.V1ObjectMeta(
            name=omnigent_settings.OMNIGENT_VOLUME_NAME,
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "omnigent-server"},
        ),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1VolumeResourceRequirements(requests={"storage": "10Gi"}),
        ),
    )


def build_omnigent_deployment(namespace: str, env: str, llm_env: dict = None) -> client.V1Deployment:
    """Omnigent Server Deployment spec."""
    is_cloud = env != "local"
    image_pull_policy = "Always" if is_cloud else "IfNotPresent"

    resources = (
        client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "1", "memory": "2Gi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "200m", "memory": "256Mi"},
            limits={"cpu": "1", "memory": "1Gi"},
        )
    )

    db_url = "sqlite:////data/omnigent.db"
    if getattr(settings, "DATA_DB_URL", None):
        db_url = settings.DATA_DB_URL
    elif getattr(settings, "PG_HOST", None) and settings.PG_HOST != "localhost":
        db_url = f"postgresql://{settings.PG_USER}:{settings.PG_PASSWORD}@{settings.PG_HOST}:{settings.PG_PORT}/omnigent"

    env_vars = [
        client.V1EnvVar(name="PORT", value="6767"),
        client.V1EnvVar(name="HOST", value="0.0.0.0"),
        client.V1EnvVar(name="DATABASE_URL", value=db_url),
        client.V1EnvVar(name="OMNIGENT_AUTH_PROVIDER", value="header"),
        client.V1EnvVar(name="OMNIGENT_LOCAL_SINGLE_USER", value="1"),
        client.V1EnvVar(name="ARTIFACT_DIR", value="/data/artifacts"),
    ]

    if llm_env:
        for k, v in llm_env.items():
            env_vars.append(client.V1EnvVar(name=k, value=str(v)))

    labels = {"app": "compassx", "compassx/service": "omnigent-server"}

    container = client.V1Container(
        name="omnigent-server",
        image=omnigent_settings.OMNIGENT_IMAGE,
        image_pull_policy=image_pull_policy,
        env=env_vars,
        ports=[client.V1ContainerPort(container_port=6767, name="http")],
        volume_mounts=[
            client.V1VolumeMount(
                name="omnigent-data",
                mount_path="/data",
            )
        ],
        resources=resources,
        readiness_probe=client.V1Probe(
            http_get=client.V1HTTPGetAction(path="/health", port=6767),
            initial_delay_seconds=3,
            period_seconds=5,
        ),
    )

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=omnigent_settings.OMNIGENT_CONTAINER_NAME,
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            strategy=client.V1DeploymentStrategy(type="Recreate"),
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    containers=[container],
                    volumes=[
                        client.V1Volume(
                            name="omnigent-data",
                            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=omnigent_settings.OMNIGENT_VOLUME_NAME
                            ),
                        )
                    ],
                ),
            ),
        ),
    )


def build_omnigent_service(namespace: str, env: str) -> client.V1Service:
    """ClusterIP Service for Omnigent Server."""
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=omnigent_settings.OMNIGENT_CONTAINER_NAME,
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "omnigent-server"},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "compassx", "compassx/service": "omnigent-server"},
            ports=[client.V1ServicePort(name="http", port=6767, target_port=6767)],
            type="ClusterIP",
        ),
    )


def build_omnigent_ingress(namespace: str, env: str, host: str) -> client.V1Ingress:
    """Ingress resource exposing Omnigent Server at devstudio.<base_domain> and /devstudio with dual routing."""
    path_host = client.V1HTTPIngressPath(
        path="/()(.*)",
        path_type="ImplementationSpecific",
        backend=client.V1IngressBackend(
            service=client.V1IngressServiceBackend(
                name=omnigent_settings.OMNIGENT_CONTAINER_NAME,
                port=client.V1ServiceBackendPort(number=6767),
            )
        ),
    )

    rule_host = client.V1IngressRule(
        host=host,
        http=client.V1HTTPIngressRuleValue(paths=[path_host]),
    )

    path_universal = client.V1HTTPIngressPath(
        path="/devstudio(/|$)(.*)",
        path_type="ImplementationSpecific",
        backend=client.V1IngressBackend(
            service=client.V1IngressServiceBackend(
                name=omnigent_settings.OMNIGENT_CONTAINER_NAME,
                port=client.V1ServiceBackendPort(number=6767),
            )
        ),
    )

    rule_universal = client.V1IngressRule(
        http=client.V1HTTPIngressRuleValue(paths=[path_universal]),
    )

    ingress_spec = client.V1IngressSpec(
        ingress_class_name=settings.K8S_INGRESS_CLASS,
        rules=[rule_host, rule_universal],
    )
    if settings.K8S_INGRESS_TLS_SECRET:
        ingress_spec.tls = [
            client.V1IngressTLS(hosts=[host], secret_name=settings.K8S_INGRESS_TLS_SECRET)
        ]

    return client.V1Ingress(
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(
            name=f"{omnigent_settings.OMNIGENT_CONTAINER_NAME}-ingress",
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "omnigent-server"},
            annotations={
                "nginx.ingress.kubernetes.io/ssl-redirect": "false",
                "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
                "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
                "nginx.ingress.kubernetes.io/websocket-services": omnigent_settings.OMNIGENT_CONTAINER_NAME,
                "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                "nginx.ingress.kubernetes.io/use-regex": "true",
            },
        ),
        spec=ingress_spec,
    )
