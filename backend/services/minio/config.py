"""MinIO service configuration."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MinioSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MINIO_IMAGE: str = Field(
        default="minio/minio:RELEASE.2025-02-28T09-55-16Z",
        alias="COMPASSX_MINIO_IMAGE",
    )
    MINIO_NAMESPACE: str = Field(default="compassx-jobs", alias="COMPASSX_MINIO_NAMESPACE")
    MINIO_DEPLOYMENT_NAME: str = Field(default="compassx-minio", alias="COMPASSX_MINIO_DEPLOYMENT_NAME")
    MINIO_SERVICE_NAME: str = Field(default="minio", alias="COMPASSX_MINIO_SERVICE_NAME")
    MINIO_CONSOLE_SERVICE_NAME: str = Field(
        default="minio-console",
        alias="COMPASSX_MINIO_CONSOLE_SERVICE_NAME",
    )
    MINIO_PORT: int = Field(default=9000, alias="COMPASSX_MINIO_PORT")
    MINIO_CONSOLE_PORT: int = Field(default=9001, alias="COMPASSX_MINIO_CONSOLE_PORT")
    MINIO_CONSOLE_SERVICE_TYPE: str = Field(
        default="LoadBalancer",
        alias="COMPASSX_MINIO_CONSOLE_SERVICE_TYPE",
    )
    MINIO_CONSOLE_NODE_PORT: int | None = Field(
        default=None,
        alias="COMPASSX_MINIO_CONSOLE_NODE_PORT",
    )
    MINIO_CONSOLE_LOAD_BALANCER_IP: str = Field(
        default="",
        alias="COMPASSX_MINIO_CONSOLE_LOAD_BALANCER_IP",
    )
    MINIO_CONSOLE_EXTERNAL_URL: str = Field(
        default="",
        alias="COMPASSX_MINIO_CONSOLE_EXTERNAL_URL",
    )
    MINIO_LOCAL_ACCESS_MODE: str = Field(
        default="port-forward",
        alias="COMPASSX_MINIO_LOCAL_ACCESS_MODE",
    )
    MINIO_ROOT_USER: str = Field(default="minioadmin", alias="COMPASSX_MINIO_ROOT_USER")
    MINIO_ROOT_PASSWORD: str = Field(default="minioadmin", alias="COMPASSX_MINIO_ROOT_PASSWORD")
    MINIO_PVC_NAME: str = Field(default="compassx-minio-data", alias="COMPASSX_MINIO_PVC_NAME")
    MINIO_STORAGE_SIZE: str = Field(default="10Gi", alias="COMPASSX_MINIO_STORAGE_SIZE")


minio_settings = MinioSettings()
