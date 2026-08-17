"""Builds K8s specs for the Airflow Deployment and Service."""
from kubernetes import client

from services.airflow.config import airflow_settings
from services.storage.config import storage_settings

_AIRFLOW_ROLE_NAME = "compassx-airflow-role"
_AIRFLOW_ROLE_BINDING_NAME = "compassx-airflow-rolebinding"


def build_airflow_service_account(namespace: str) -> client.V1ServiceAccount:
    return client.V1ServiceAccount(
        api_version="v1",
        kind="ServiceAccount",
        metadata=client.V1ObjectMeta(
            name=airflow_settings.AIRFLOW_SERVICE_ACCOUNT_NAME,
            namespace=namespace,
        ),
    )


def build_airflow_role(namespace: str) -> client.V1Role:
    return client.V1Role(
        api_version="rbac.authorization.k8s.io/v1",
        kind="Role",
        metadata=client.V1ObjectMeta(name=_AIRFLOW_ROLE_NAME, namespace=namespace),
        rules=[
            client.V1PolicyRule(
                api_groups=[""],
                resources=["pods"],
                verbs=["create", "delete", "get", "list", "patch", "watch"],
            ),
            client.V1PolicyRule(
                api_groups=[""],
                resources=["pods/log"],
                verbs=["get", "list"],
            ),
            client.V1PolicyRule(
                api_groups=[""],
                resources=["events"],
                verbs=["get", "list", "watch"],
            ),
        ],
    )


def build_airflow_role_binding(namespace: str) -> client.V1RoleBinding:
    return client.V1RoleBinding(
        api_version="rbac.authorization.k8s.io/v1",
        kind="RoleBinding",
        metadata=client.V1ObjectMeta(name=_AIRFLOW_ROLE_BINDING_NAME, namespace=namespace),
        subjects=[
            client.RbacV1Subject(
                kind="ServiceAccount",
                name=airflow_settings.AIRFLOW_SERVICE_ACCOUNT_NAME,
                namespace=namespace,
            )
        ],
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name=_AIRFLOW_ROLE_NAME,
        ),
    )


def _build_airflow_env(dags_mount_path: str) -> list[client.V1EnvVar]:
    return [
        client.V1EnvVar(name="AIRFLOW_HOME", value="/opt/airflow"),
        client.V1EnvVar(name="AIRFLOW__CORE__EXECUTOR", value="CeleryExecutor"),
        client.V1EnvVar(name="AIRFLOW__CORE__HOSTNAME_CALLABLE", value="socket:getfqdn"),
        client.V1EnvVar(name="AIRFLOW__CORE__LOAD_EXAMPLES", value="False"),
        client.V1EnvVar(name="AIRFLOW__CORE__DAGS_FOLDER", value=dags_mount_path),
        client.V1EnvVar(name="AIRFLOW__LOGGING__BASE_LOG_FOLDER", value=airflow_settings.AIRFLOW_LOGS_DIR),
        client.V1EnvVar(name="AIRFLOW__LOGGING__WORKER_LOG_SERVER_PORT", value="8793"),
        client.V1EnvVar(name="AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION", value="False"),
        client.V1EnvVar(name="AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL", value="10"),
        client.V1EnvVar(name="AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL", value="5"),
        client.V1EnvVar(name="AIRFLOW__CORE__MIN_SERIALIZED_DAG_UPDATE_INTERVAL", value="0"),
        client.V1EnvVar(name="AIRFLOW__CORE__MIN_SERIALIZED_DAG_FETCH_INTERVAL", value="0"),
        client.V1EnvVar(name="AIRFLOW__CORE__PARALLELISM", value="4"),
        client.V1EnvVar(name="AIRFLOW__CORE__DAG_CONCURRENCY", value="2"),
        client.V1EnvVar(
            name="AIRFLOW__DATABASE__SQL_ALCHEMY_CONN",
            value=airflow_settings.sqlalchemy_conn(),
        ),
        client.V1EnvVar(
            name="AIRFLOW__CELERY__BROKER_URL",
            value=airflow_settings.redis_broker_url(),
        ),
        client.V1EnvVar(
            name="AIRFLOW__CELERY__RESULT_BACKEND",
            value=airflow_settings.celery_result_backend(),
        ),
        client.V1EnvVar(name="AIRFLOW__CELERY__POOL", value="solo"),
        client.V1EnvVar(name="AIRFLOW__WEBSERVER__EXPOSE_CONFIG", value="False"),
        client.V1EnvVar(name="AIRFLOW__WEBSERVER__WORKER_TIMEOUT", value="300"),
        client.V1EnvVar(name="AIRFLOW__WEBSERVER__WORKERS", value="1"),
        client.V1EnvVar(name="AIRFLOW__WEBSERVER__HIDE_PAUSED_DAGS_BY_DEFAULT", value="False"),
        client.V1EnvVar(
            name="AIRFLOW__WEBSERVER__BASE_URL",
            value=airflow_settings.AIRFLOW_WEBSERVER_BASE_URL or airflow_settings.ui_url(),
        ),
        client.V1EnvVar(
            name="AIRFLOW__WEBSERVER__WEB_SERVER_URL_PREFIX",
            value=airflow_settings.AIRFLOW_WEBSERVER_URL_PREFIX,
        ),
        client.V1EnvVar(
            name="AIRFLOW__WEBSERVER__ENABLE_PROXY_FIX",
            value="true" if airflow_settings.AIRFLOW_WEBSERVER_ENABLE_PROXY_FIX else "false",
        ),
        client.V1EnvVar(
            name="AIRFLOW__API__AUTH_BACKENDS",
            value="airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session",
        ),
        client.V1EnvVar(name="COMPASSX_BACKEND_API_URL", value=airflow_settings.backend_api_url()),
        client.V1EnvVar(name="COMPASSX_BACKEND_URL", value=airflow_settings.backend_api_url()),
        client.V1EnvVar(name="COMPASSX_SYSTEM_DB_URL", value=airflow_settings.system_db_url()),
        client.V1EnvVar(name="COMPASSX_INTERNAL_SECRET", value=airflow_settings.AIRFLOW_CALLBACK_SECRET),
        client.V1EnvVar(name="COMPASSX_DAG_SHARD_COUNT", value="1"),
    ]


def _build_webserver_resources(env: str) -> client.V1ResourceRequirements:
    is_cloud = env != "local"
    return (
        client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "500m", "memory": "1Gi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "384Mi"},
            limits={"cpu": "1", "memory": "768Mi"},
        )
    )


def _build_scheduler_resources(env: str) -> client.V1ResourceRequirements:
    is_cloud = env != "local"
    return (
        client.V1ResourceRequirements(
            requests={"cpu": "200m", "memory": "192Mi"},
            limits={"cpu": "300m", "memory": "512Mi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "384Mi"},
            limits={"cpu": "1", "memory": "768Mi"},
        )
    )


def _build_worker_resources(env: str) -> client.V1ResourceRequirements:
    is_cloud = env != "local"
    return (
        client.V1ResourceRequirements(
            requests={"cpu": "200m", "memory": "256Mi"},
            limits={"cpu": "400m", "memory": "768Mi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "384Mi"},
            limits={"cpu": "1", "memory": "768Mi"},
        )
    )


def _build_redis_resources(env: str) -> client.V1ResourceRequirements:
    is_cloud = env != "local"
    return (
        client.V1ResourceRequirements(
            requests={"cpu": "50m", "memory": "64Mi"},
            limits={"cpu": "100m", "memory": "128Mi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "100m", "memory": "128Mi"},
            limits={"cpu": "250m", "memory": "256Mi"},
        )
    )


def _build_dag_sync_sidecar(dags_mount_path: str) -> client.V1Container:
    dags_prefix = storage_settings.STORAGE_DAGS_PREFIX.strip("/")
    remote_dag_path = (
        f"local/{storage_settings.STORAGE_DAGS_BUCKET}/{dags_prefix}"
        if dags_prefix
        else f"local/{storage_settings.STORAGE_DAGS_BUCKET}"
    )
    dag_mirror_command = (
        "mc alias set local "
        f"{storage_settings.MINIO_INTERNAL_ENDPOINT} "
        f"{storage_settings.MINIO_ACCESS_KEY} "
        f"{storage_settings.MINIO_SECRET_KEY} && "
        f"mc mb --ignore-existing local/{storage_settings.STORAGE_DAGS_BUCKET} && "
        "while true; do "
        f"if mc ls {remote_dag_path} >/dev/null 2>&1; then "
        f"mc mirror --overwrite --remove {remote_dag_path} {dags_mount_path}; "
        f"else rm -f {dags_mount_path}/*.py; "
        "fi; "
        "sleep 5; "
        "done"
    )
    return client.V1Container(
        name="dag-sync",
        image=airflow_settings.AIRFLOW_DAG_SYNC_IMAGE,
        command=["sh", "-c", dag_mirror_command],
        env=[
            client.V1EnvVar(name="HOME", value="/tmp"),
            client.V1EnvVar(name="MC_CONFIG_DIR", value="/tmp/.mc"),
        ],
        volume_mounts=[client.V1VolumeMount(name="airflow-dags", mount_path=dags_mount_path)],
    )


def _build_logs_init_container(logs_mount_path: str, image: str, image_pull_policy: str) -> client.V1Container:
    return client.V1Container(
        name="init-airflow-logs",
        image=image,
        image_pull_policy=image_pull_policy,
        command=["bash", "-lc"],
        args=[
            (
                f"mkdir -p {logs_mount_path}/scheduler {logs_mount_path}/dag_processor_manager "
                f"{logs_mount_path}/webserver {logs_mount_path}/worker && "
                f"chown -R {airflow_settings.AIRFLOW_UID}:{airflow_settings.AIRFLOW_GID} {logs_mount_path} && "
                f"chmod -R g+rwX {logs_mount_path}"
            )
        ],
        security_context=client.V1SecurityContext(run_as_user=0),
        volume_mounts=[client.V1VolumeMount(name="airflow-logs", mount_path=logs_mount_path)],
    )


def _build_airflow_runtime_deployment(
    namespace: str,
    env: str,
    *,
    deployment_name: str,
    service_label: str,
    container_name: str,
    args: list[str],
    resources: client.V1ResourceRequirements,
    include_http_port: bool = False,
    add_web_probes: bool = False,
) -> client.V1Deployment:
    is_cloud = env != "local"
    image_pull_policy = "Always" if is_cloud else "IfNotPresent"
    dags_mount_path = "/opt/airflow/dags"
    logs_mount_path = airflow_settings.AIRFLOW_LOGS_DIR
    labels = {"app": "compassx", "compassx/service": service_label}
    health_path = (
        f"{airflow_settings.AIRFLOW_WEBSERVER_URL_PREFIX.rstrip('/')}/health"
        if airflow_settings.AIRFLOW_WEBSERVER_URL_PREFIX
        else "/health"
    )

    airflow_container = client.V1Container(
        name=container_name,
        image=airflow_settings.AIRFLOW_IMAGE,
        image_pull_policy=image_pull_policy,
        command=["airflow"],
        args=args,
        env=_build_airflow_env(dags_mount_path),
        ports=(
            [client.V1ContainerPort(container_port=airflow_settings.AIRFLOW_PORT, name="http")]
            if include_http_port
            else None
        ),
        volume_mounts=[
            client.V1VolumeMount(name="airflow-dags", mount_path=dags_mount_path),
            client.V1VolumeMount(name="airflow-logs", mount_path=logs_mount_path),
        ],
        resources=resources,
        startup_probe=(
            client.V1Probe(
                http_get=client.V1HTTPGetAction(path=health_path, port=airflow_settings.AIRFLOW_PORT),
                initial_delay_seconds=30,
                period_seconds=10,
                timeout_seconds=5,
                failure_threshold=60,
            )
            if add_web_probes
            else None
        ),
        readiness_probe=(
            client.V1Probe(
                http_get=client.V1HTTPGetAction(path=health_path, port=airflow_settings.AIRFLOW_PORT),
                initial_delay_seconds=60,
                period_seconds=10,
                timeout_seconds=5,
                failure_threshold=6,
            )
            if add_web_probes
            else None
        ),
        liveness_probe=(
            client.V1Probe(
                http_get=client.V1HTTPGetAction(path=health_path, port=airflow_settings.AIRFLOW_PORT),
                initial_delay_seconds=180,
                period_seconds=20,
                timeout_seconds=5,
                failure_threshold=6,
            )
            if add_web_probes
            else None
        ),
    )

    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=deployment_name,
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels=labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    service_account_name=airflow_settings.AIRFLOW_SERVICE_ACCOUNT_NAME,
                    security_context=client.V1PodSecurityContext(
                        run_as_user=airflow_settings.AIRFLOW_UID,
                        fs_group=airflow_settings.AIRFLOW_GID,
                    ),
                    init_containers=[
                        _build_logs_init_container(logs_mount_path, airflow_settings.AIRFLOW_IMAGE, image_pull_policy)
                    ],
                    containers=[airflow_container, _build_dag_sync_sidecar(dags_mount_path)],
                    volumes=[
                        client.V1Volume(
                            name="airflow-dags",
                            empty_dir=client.V1EmptyDirVolumeSource(),
                        ),
                        client.V1Volume(
                            name="airflow-logs",
                            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                claim_name=airflow_settings.AIRFLOW_LOGS_PVC_NAME
                            ),
                        ),
                    ],
                ),
            ),
        ),
    )


def build_airflow_init_job(namespace: str, env: str) -> client.V1Job:
    is_cloud = env != "local"
    image_pull_policy = "Always" if is_cloud else "IfNotPresent"
    resources = (
        client.V1ResourceRequirements(
            requests={"cpu": "100m", "memory": "192Mi"},
            limits={"cpu": "300m", "memory": "512Mi"},
        )
        if is_cloud
        else client.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "1", "memory": "1536Mi"},
        )
    )
    labels = {"app": "compassx", "compassx/service": "airflow-init"}
    bootstrap_script = "\n".join(
        [
            "set -e",
            "mkdir -p /tmp/empty-dags",
            "AIRFLOW__CORE__DAGS_FOLDER=/tmp/empty-dags airflow db migrate",
            (
                "airflow users create "
                f"--username {airflow_settings.AIRFLOW_ADMIN_USERNAME} "
                f"--password {airflow_settings.AIRFLOW_ADMIN_PASSWORD} "
                f"--firstname {airflow_settings.AIRFLOW_ADMIN_FIRSTNAME} "
                f"--lastname {airflow_settings.AIRFLOW_ADMIN_LASTNAME} "
                f"--role Admin "
                f"--email {airflow_settings.AIRFLOW_ADMIN_EMAIL} || true"
            ),
        ]
    )

    container = client.V1Container(
        name="airflow-init",
        image=airflow_settings.AIRFLOW_IMAGE,
        image_pull_policy=image_pull_policy,
        command=["bash", "-lc"],
        args=[bootstrap_script],
        env=_build_airflow_env("/tmp/empty-dags"),
        resources=resources,
    )

    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=airflow_settings.AIRFLOW_INIT_JOB_NAME,
            namespace=namespace,
            labels=labels,
        ),
        spec=client.V1JobSpec(
            backoff_limit=1,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    service_account_name=airflow_settings.AIRFLOW_SERVICE_ACCOUNT_NAME,
                    containers=[container],
                ),
            ),
        ),
    )


def build_airflow_webserver_deployment(namespace: str, env: str) -> client.V1Deployment:
    return _build_airflow_runtime_deployment(
        namespace,
        env,
        deployment_name=airflow_settings.AIRFLOW_WEBSERVER_DEPLOYMENT_NAME,
        service_label="airflow-web",
        container_name="webserver",
        args=["webserver"],
        resources=_build_webserver_resources(env),
        include_http_port=True,
        add_web_probes=True,
    )


def build_airflow_scheduler_deployment(namespace: str, env: str) -> client.V1Deployment:
    return _build_airflow_runtime_deployment(
        namespace,
        env,
        deployment_name=airflow_settings.AIRFLOW_SCHEDULER_DEPLOYMENT_NAME,
        service_label="airflow-scheduler",
        container_name="scheduler",
        args=["scheduler"],
        resources=_build_scheduler_resources(env),
    )


def build_airflow_worker_deployment(namespace: str, env: str) -> client.V1Deployment:
    return _build_airflow_runtime_deployment(
        namespace,
        env,
        deployment_name=airflow_settings.AIRFLOW_WORKER_DEPLOYMENT_NAME,
        service_label="airflow-worker",
        container_name="worker",
        args=["celery", "worker"],
        resources=_build_worker_resources(env),
    )


def build_airflow_redis_deployment(namespace: str, env: str) -> client.V1Deployment:
    labels = {"app": "compassx", "compassx/service": "airflow-redis"}
    return client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=airflow_settings.AIRFLOW_REDIS_DEPLOYMENT_NAME,
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
                            name="redis",
                            image="redis:7",
                            ports=[client.V1ContainerPort(container_port=6379, name="redis")],
                            resources=_build_redis_resources(env),
                        )
                    ]
                ),
            ),
        ),
    )


def build_airflow_service(namespace: str, env: str) -> client.V1Service:
    is_local = env == "local"
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=airflow_settings.AIRFLOW_SERVICE_NAME,
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "airflow-web"},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "compassx", "compassx/service": "airflow-web"},
            ports=[
                client.V1ServicePort(
                    port=airflow_settings.AIRFLOW_PORT,
                    target_port=airflow_settings.AIRFLOW_PORT,
                    name="http",
                )
            ],
            type="NodePort" if is_local else "ClusterIP",
        ),
    )


def build_airflow_redis_service(namespace: str) -> client.V1Service:
    return client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(
            name=airflow_settings.AIRFLOW_REDIS_SERVICE_NAME,
            namespace=namespace,
            labels={"app": "compassx", "compassx/service": "airflow-redis"},
        ),
        spec=client.V1ServiceSpec(
            selector={"app": "compassx", "compassx/service": "airflow-redis"},
            ports=[
                client.V1ServicePort(
                    port=6379,
                    target_port=6379,
                    name="redis",
                )
            ],
            type="ClusterIP",
        ),
    )


def build_airflow_dags_pvc(namespace: str) -> client.V1PersistentVolumeClaim:
    return client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=client.V1ObjectMeta(name=airflow_settings.AIRFLOW_DAGS_PVC_NAME, namespace=namespace),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1VolumeResourceRequirements(
                requests={"storage": airflow_settings.AIRFLOW_DAGS_STORAGE_SIZE}
            ),
        ),
    )


def build_airflow_logs_pvc(namespace: str) -> client.V1PersistentVolumeClaim:
    return client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=client.V1ObjectMeta(name=airflow_settings.AIRFLOW_LOGS_PVC_NAME, namespace=namespace),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=[airflow_settings.AIRFLOW_LOGS_PVC_ACCESS_MODE],
            storage_class_name=airflow_settings.AIRFLOW_LOGS_PVC_STORAGE_CLASS_NAME,
            resources=client.V1VolumeResourceRequirements(
                requests={"storage": airflow_settings.AIRFLOW_LOGS_STORAGE_SIZE}
            ),
        ),
    )
