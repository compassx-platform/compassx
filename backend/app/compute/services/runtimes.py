"""Pod spec builders — one per supported runtime."""
import logging
from kubernetes import client

from compute.config import compute_settings
from compute.profiles import ComputeProfile

logger = logging.getLogger(__name__)

# Runtime image constants
SPARK_IMAGE = "apache/spark:3.5.0"
FLINK_IMAGE = "flink:1.18-scala_2.12"
RAY_IMAGE = "rayproject/ray:2.9.0"
DUCKDB_IMAGE = "compassx-compute-duckdb:latest"

# Runtimes valid only with certain profiles
DUCKDB_VALID_PROFILES = {"local", "cloud-xs", "cloud-s"}


def _minio_env_vars() -> list[client.V1EnvVar]:
    """MinIO/S3 environment variables injected on every container."""
    return [
        client.V1EnvVar(name="AWS_ENDPOINT_URL", value=f"http://{compute_settings.MINIO_ENDPOINT}"),
        client.V1EnvVar(name="AWS_ACCESS_KEY_ID", value=compute_settings.MINIO_ACCESS_KEY),
        client.V1EnvVar(name="AWS_SECRET_ACCESS_KEY", value=compute_settings.MINIO_SECRET_KEY),
        client.V1EnvVar(name="AWS_DEFAULT_REGION", value="us-east-1"),
    ]


def _resolve_image(image: str) -> str:
    """Resolve the final image path, prefixing with the compute registry prefix if configured."""
    prefix = compute_settings.COMPUTE_REGISTRY_PREFIX
    if prefix:
        prefix_clean = prefix.rstrip("/")
        if not image.startswith(prefix_clean):
            return f"{prefix_clean}/{image}"
    return image


def _image_pull_policy(env: str) -> str:
    """Always pull in cloud to ensure latest ACR images, but use IfNotPresent for local dev."""
    return "Always" if env != "local" else "IfNotPresent"


def _standard_labels(
    job_id: str,
    user_id: str,
    runtime: str,
    resource_id: str | None = None,
) -> dict[str, str]:
    """Labels applied to every pod."""
    labels = {
        "app": "compassx",
        "runtime": runtime,
        "user": user_id,
        "compassx/job": job_id,
    }
    if resource_id:
        labels["compassx/resource"] = resource_id
    return labels


def _standard_annotations(profile: ComputeProfile, env: str) -> dict[str, str]:
    """Annotations applied to every pod."""
    from datetime import datetime, timezone
    return {
        "compassx/created-at": datetime.now(timezone.utc).isoformat(),
        "compassx/profile": profile.id,
        "compassx/env": env,
    }


def _resource_requirements(profile: ComputeProfile) -> client.V1ResourceRequirements:
    """Build ResourceRequirements from a ComputeProfile."""
    return client.V1ResourceRequirements(
        requests=profile.requests,
        limits=profile.limits,
    )


def _build_spark_container(
    profile: ComputeProfile,
    env: str,
    extra_env: dict | None,
) -> client.V1Container:
    """Build the Spark container spec."""
    env_vars = _minio_env_vars() + [
        client.V1EnvVar(name="SPARK_MODE", value="master"),
        client.V1EnvVar(name="SPARK_MASTER_URL", value="spark://localhost:7077"),
        client.V1EnvVar(name="SPARK_WORKER_MEMORY", value=profile.limits.get("memory", "1g")),
    ]
    if extra_env:
        env_vars += [client.V1EnvVar(name=k, value=v) for k, v in extra_env.items()]
    return client.V1Container(
        name="spark",
        image=_resolve_image(profile.limits.get("_custom_image") or SPARK_IMAGE),
        command=["/opt/spark/bin/spark-class", "org.apache.spark.deploy.master.Master"],
        env=env_vars,
        resources=_resource_requirements(profile),
        image_pull_policy=_image_pull_policy(env),
    )


def _build_flink_container(
    profile: ComputeProfile,
    env: str,
    extra_env: dict | None,
) -> client.V1Container:
    """Build the Flink container spec."""
    heap_mb = _parse_memory_mb(profile.limits.get("memory", "1Gi"))
    flink_props = f"jobmanager.heap.size: {heap_mb}m\ntaskmanager.memory.process.size: {heap_mb}m\n"
    env_vars = _minio_env_vars() + [
        client.V1EnvVar(name="FLINK_PROPERTIES", value=flink_props),
    ]
    if extra_env:
        env_vars += [client.V1EnvVar(name=k, value=v) for k, v in extra_env.items()]
    return client.V1Container(
        name="flink",
        image=_resolve_image(FLINK_IMAGE),
        env=env_vars,
        resources=_resource_requirements(profile),
        image_pull_policy=_image_pull_policy(env),
        ports=[
            client.V1ContainerPort(container_port=8081, name="rest"),
            client.V1ContainerPort(container_port=6123, name="rpc"),
        ],
    )


def _build_ray_container(
    profile: ComputeProfile,
    env: str,
    extra_env: dict | None,
) -> client.V1Container:
    """Build the Ray container spec."""
    env_vars = _minio_env_vars() + [
        client.V1EnvVar(name="RAY_DISABLE_MEMORY_MONITOR", value="1"),
    ]
    if extra_env:
        env_vars += [client.V1EnvVar(name=k, value=v) for k, v in extra_env.items()]
    return client.V1Container(
        name="ray",
        image=_resolve_image(RAY_IMAGE),
        command=["ray", "start", "--head", "--dashboard-host=0.0.0.0"],
        env=env_vars,
        resources=_resource_requirements(profile),
        image_pull_policy=_image_pull_policy(env),
        ports=[
            client.V1ContainerPort(container_port=8265, name="dashboard"),
            client.V1ContainerPort(container_port=6379, name="redis"),
            client.V1ContainerPort(container_port=10001, name="client"),
        ],
    )


def _build_duckdb_container(
    profile: ComputeProfile,
    env: str,
    extra_env: dict | None,
) -> client.V1Container:
    """Build the DuckDB container spec.

    The pod stays alive with a sleep loop; Enterprise Gateway execs
    ipykernel into it on demand — no JupyterLab needed here.
    """
    env_vars = _minio_env_vars()
    if extra_env:
        env_vars += [client.V1EnvVar(name=k, value=v) for k, v in extra_env.items()]
    return client.V1Container(
        name="duckdb",
        image=_resolve_image(DUCKDB_IMAGE),
        command=["tail", "-f", "/dev/null"],
        env=env_vars,
        resources=_resource_requirements(profile),
        image_pull_policy=_image_pull_policy(env),
    )


def _parse_memory_mb(mem_str: str) -> int:
    """Convert K8s memory string to integer MB."""
    mem_str = mem_str.strip()
    if mem_str.endswith("Gi"):
        return int(mem_str[:-2]) * 1024
    if mem_str.endswith("Mi"):
        return int(mem_str[:-2])
    if mem_str.endswith("G") or mem_str.endswith("g"):
        return int(mem_str[:-1]) * 1024
    if mem_str.endswith("M") or mem_str.endswith("m"):
        return int(mem_str[:-1])
    return 512  # fallback


_CONTAINER_BUILDERS = {
    "spark": _build_spark_container,
    "flink": _build_flink_container,
    "ray": _build_ray_container,
    "duckdb": _build_duckdb_container,
}


def build_pod_spec(
    job_id: str,
    user_id: str,
    runtime: str,
    profile: ComputeProfile,
    namespace: str,
    env: str,
    custom_image: str | None = None,
    extra_env: dict | None = None,
    resource_id: str | None = None,
) -> client.V1Pod:
    """Build a V1Pod for the given runtime and profile.

    Args:
        job_id: Unique job identifier.
        user_id: ID of the submitting user.
        runtime: One of spark | flink | ray | duckdb.
        profile: Resolved ComputeProfile.
        namespace: Target K8s namespace.
        env: compassx environment (local|cloud).
        custom_image: Override the default runtime image.
        extra_env: Additional env vars injected into the container.

    Returns:
        A V1Pod ready for submission.
    """
    if runtime == "duckdb" and profile.id not in DUCKDB_VALID_PROFILES:
        raise ValueError(
            f"DuckDB is only valid with profiles: {', '.join(DUCKDB_VALID_PROFILES)}"
        )

    builder = _CONTAINER_BUILDERS.get(runtime)
    if builder is None:
        raise ValueError(f"Unknown runtime: {runtime}")

    container = builder(profile, env, extra_env)
    if custom_image:
        container.image = custom_image

    pod_name = f"compassx-{runtime}-{job_id}"

    # TODO: TESTING ONLY — For local minikube with image pull cert issues.
    # Remove or conditionally apply based on COMPASSX_ENV in production.
    # In production, use proper image registries with valid certs and auth.
    pod_spec_kwargs = {
        "containers": [container],
        "restart_policy": "Never",
    }

    # Add image pull secrets if configured (for private registries in prod)
    # Currently minikube bypasses cert check — this is a temp workaround

    pod = client.V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=client.V1ObjectMeta(
            name=pod_name,
            namespace=namespace,
            labels=_standard_labels(job_id, user_id, runtime, resource_id=resource_id),
            annotations=_standard_annotations(profile, env),
        ),
        spec=client.V1PodSpec(**pod_spec_kwargs),
    )

    logger.debug(
        "Pod spec built: job_id=%s runtime=%s profile=%s env=%s",
        job_id, runtime, profile.id, env,
    )
    return pod


def build_deployment_spec(
    deployment_name: str,
    resource_id: str,
    user_id: str,
    runtime: str,
    profile: ComputeProfile,
    namespace: str,
    env: str,
    custom_image: str | None = None,
    extra_env: dict | None = None,
    replicas: int = 1,
) -> client.V1Deployment:
    """Build a deployment that keeps a compute runtime alive."""
    pod = build_pod_spec(
        job_id=resource_id,
        user_id=user_id,
        runtime=runtime,
        profile=profile,
        namespace=namespace,
        env=env,
        custom_image=custom_image,
        extra_env=extra_env,
        resource_id=resource_id,
    )
    pod.metadata.name = None
    pod.spec.restart_policy = "Always"
    selector_labels = {
        "app": "compassx",
        "compassx/resource": resource_id,
    }
    pod.metadata.labels = {**(pod.metadata.labels or {}), **selector_labels}

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=deployment_name,
            namespace=namespace,
            labels=pod.metadata.labels,
            annotations=pod.metadata.annotations,
        ),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(match_labels=selector_labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels=pod.metadata.labels,
                    annotations=pod.metadata.annotations,
                ),
                spec=pod.spec,
            ),
        ),
    )
