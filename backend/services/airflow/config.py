"""Airflow service configuration."""
from pathlib import Path
from urllib.parse import quote_plus

from compute.config import compute_settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class AirflowSettings(BaseSettings):
    """Airflow-specific environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    AIRFLOW_IMAGE: str = "apache/airflow:2.9.3-python3.11"
    AIRFLOW_PIP_PACKAGES: str = "apache-airflow-providers-cncf-kubernetes kubernetes"
    AIRFLOW_SERVICE_ACCOUNT_NAME: str = "compassx-airflow"
    AIRFLOW_NOTEBOOK_RUNNER_IMAGE: str = "compassx-airflow-notebook-runner:latest"
    AIRFLOW_NOTEBOOK_RUNNER_IMAGE_PULL_POLICY: str = ""
    AIRFLOW_NOTEBOOK_ROOT: str = "/ms-home"
    AIRFLOW_NOTEBOOK_POD_SERVICE_ACCOUNT_NAME: str = "compassx-airflow"
    AIRFLOW_PORT: int = 8080
    AIRFLOW_DAG_SYNC_IMAGE: str = "minio/mc:RELEASE.2025-03-12T17-29-24Z"
    AIRFLOW_NAMESPACE: str = compute_settings.COMPASSX_NAMESPACE
    AIRFLOW_WEBSERVER_DEPLOYMENT_NAME: str = "compassx-airflow-web"
    AIRFLOW_SCHEDULER_DEPLOYMENT_NAME: str = "compassx-airflow-scheduler"
    AIRFLOW_WORKER_DEPLOYMENT_NAME: str = "compassx-airflow-worker"
    AIRFLOW_REDIS_DEPLOYMENT_NAME: str = "compassx-airflow-redis"
    AIRFLOW_SERVICE_NAME: str = "compassx-airflow"
    AIRFLOW_REDIS_SERVICE_NAME: str = "airflow-redis-svc"
    AIRFLOW_INIT_JOB_NAME: str = "compassx-airflow-init"
    AIRFLOW_API_BASE_URL: str = "http://127.0.0.1:8080"
    AIRFLOW_DAGS_DIR: str = str(Path(__file__).resolve().parents[2] / "shared" / "airflow" / "dags")
    AIRFLOW_ADMIN_USERNAME: str = "admin"
    AIRFLOW_ADMIN_PASSWORD: str = "admin"
    AIRFLOW_ADMIN_EMAIL: str = "admin@compassx.local"
    AIRFLOW_ADMIN_FIRSTNAME: str = "CompassX"
    AIRFLOW_ADMIN_LASTNAME: str = "Admin"
    AIRFLOW_CONTROL_USERNAME: str = "admin"
    AIRFLOW_CONTROL_PASSWORD: str = "admin"
    AIRFLOW_CALLBACK_SECRET: str = "compassx-local-dev-secret"
    AIRFLOW_REQUEST_TIMEOUT_SECONDS: int = 15
    AIRFLOW_EXECUTION_TOKEN_TTL_SECONDS: int = 900
    COMPASSX_SYSTEM_DB_URL: str = ""
    AIRFLOW_PG_HOST: str = "host.minikube.internal"
    AIRFLOW_PG_PORT: int = 5432
    AIRFLOW_PG_USER: str = "postgres"
    AIRFLOW_PG_PASSWORD: str = "postgres"
    AIRFLOW_PG_DATABASE: str = "airflow_meta"
    AIRFLOW_BACKEND_API_URL: str = ""
    AIRFLOW_DAGS_PVC_NAME: str = "compassx-airflow-dags"
    AIRFLOW_DAGS_STORAGE_SIZE: str = "5Gi"
    AIRFLOW_LOGS_PVC_NAME: str = "compassx-airflow-logs"
    AIRFLOW_LOGS_STORAGE_SIZE: str = "10Gi"
    AIRFLOW_LOGS_PVC_ACCESS_MODE: str = "ReadWriteMany"
    AIRFLOW_LOGS_PVC_STORAGE_CLASS_NAME: str = "azurefile"
    AIRFLOW_LOGS_DIR: str = "/opt/airflow/logs"
    AIRFLOW_UID: int = 50000
    AIRFLOW_GID: int = 0
    AIRFLOW_UI_URL: str = ""
    AIRFLOW_WEBSERVER_BASE_URL: str = ""
    AIRFLOW_WEBSERVER_URL_PREFIX: str = ""
    AIRFLOW_WEBSERVER_ENABLE_PROXY_FIX: bool = False
    AIRFLOW_INIT_JOB_TIMEOUT_SECONDS: int = 300

    def redis_broker_url(self) -> str:
        return f"redis://{self.AIRFLOW_REDIS_SERVICE_NAME}:6379/0"

    def celery_result_backend(self) -> str:
        return f"db+{self.sqlalchemy_conn()}"

    def sqlalchemy_conn(self) -> str:
        password = quote_plus(self.AIRFLOW_PG_PASSWORD)
        user = quote_plus(self.AIRFLOW_PG_USER)
        database = quote_plus(self.AIRFLOW_PG_DATABASE)
        host = self.AIRFLOW_PG_HOST
        return f"postgresql+psycopg2://{user}:{password}@{host}:{self.AIRFLOW_PG_PORT}/{database}"

    def system_db_url(self) -> str:
        if self.COMPASSX_SYSTEM_DB_URL:
            return self.COMPASSX_SYSTEM_DB_URL
        password = quote_plus(self.AIRFLOW_PG_PASSWORD)
        user = quote_plus(self.AIRFLOW_PG_USER)
        host = self.AIRFLOW_PG_HOST
        return (
            f"postgresql://{user}:{password}@{host}:{self.AIRFLOW_PG_PORT}/"
            "compassx_system"
        )

    def backend_api_url(self) -> str:
        if self.AIRFLOW_BACKEND_API_URL:
            return self.AIRFLOW_BACKEND_API_URL.rstrip("/")
        from compassx.lookup import try_resolve_url
        return try_resolve_url("backend", "http://localhost:8000")

    def notebook_runner_image_pull_policy(self) -> str:
        if self.AIRFLOW_NOTEBOOK_RUNNER_IMAGE_PULL_POLICY:
            return self.AIRFLOW_NOTEBOOK_RUNNER_IMAGE_PULL_POLICY
        return "IfNotPresent" if compute_settings.is_local() else "Always"

    def api_base_url(self) -> str:
        if self.AIRFLOW_API_BASE_URL and "127.0.0.1" not in self.AIRFLOW_API_BASE_URL and "localhost" not in self.AIRFLOW_API_BASE_URL:
            return self.AIRFLOW_API_BASE_URL.rstrip("/")
        from compassx.lookup import try_resolve_url

        fallback = (
            self.AIRFLOW_API_BASE_URL.rstrip("/")
            if compute_settings.is_local()
            else f"http://{self.AIRFLOW_SERVICE_NAME}.{self.AIRFLOW_NAMESPACE}.svc.cluster.local:{self.AIRFLOW_PORT}"
        )
        return try_resolve_url("airflow", fallback)

    def ui_url(self) -> str:
        if self.AIRFLOW_UI_URL:
            return self.AIRFLOW_UI_URL.rstrip("/")
        from compassx.lookup import try_resolve_url

        fallback = (
            f"http://localhost:{self.AIRFLOW_PORT}"
            if compute_settings.is_local()
            else f"http://{self.AIRFLOW_SERVICE_NAME}.{self.AIRFLOW_NAMESPACE}.svc.cluster.local:{self.AIRFLOW_PORT}"
        )
        return try_resolve_url("airflow", fallback)


airflow_settings = AirflowSettings()
