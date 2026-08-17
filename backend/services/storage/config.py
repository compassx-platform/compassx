"""Shared storage configuration for DAGs and notebook outputs."""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    STORAGE_BACKEND: str = "minio"
    STORAGE_DAGS_BACKEND: str = "minio"
    STORAGE_DAGS_BUCKET: str = "compassx-dags"
    STORAGE_DAGS_PREFIX: str = "dags/"
    STORAGE_OUTPUTS_BUCKET: str = "compassx-outputs"
    STORAGE_OUTPUTS_PREFIX: str = "notebook-runs/"
    STORAGE_NOTEBOOKS_BUCKET: str = "compassx-notebooks"
    STORAGE_NOTEBOOKS_PREFIX: str = "notebooks/"

    MINIO_INTERNAL_ENDPOINT: str = "http://minio:9000"
    MINIO_EXTERNAL_ENDPOINT: str = "http://127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_REGION: str = "us-east-1"

    AZURE_STORAGE_ACCOUNT_URL: str = ""
    AZURE_STORAGE_ACCOUNT_NAME: str = ""
    AZURE_STORAGE_ACCOUNT_KEY: str = ""
    AZURE_STORAGE_CONNECTION_STRING: str = ""

    def outputs_object_name(self, filename: str) -> str:
        prefix = self.STORAGE_OUTPUTS_PREFIX.strip("/")
        return f"{prefix}/{filename}" if prefix else filename

    def dags_object_name(self, filename: str) -> str:
        prefix = self.STORAGE_DAGS_PREFIX.strip("/")
        return f"{prefix}/{filename}" if prefix else filename

    def notebooks_object_name(self, filename: str) -> str:
        prefix = self.STORAGE_NOTEBOOKS_PREFIX.strip("/")
        return f"{prefix}/{filename}" if prefix else filename

    def minio_endpoint_for_app(self) -> str:
        runtime_endpoint = os.environ.get("AWS_ENDPOINT_URL", "").strip()
        if runtime_endpoint:
            return runtime_endpoint
        # Standalone runtime images intentionally package only the storage
        # module. Resolve platform service discovery only in the host app.
        from compassx.lookup import try_resolve_url

        fallback = (
            self.MINIO_EXTERNAL_ENDPOINT
            if os.environ.get("COMPASSX_ENV", "local") == "local"
            else self.MINIO_INTERNAL_ENDPOINT
        )
        return try_resolve_url("minio", fallback)


storage_settings = StorageSettings()
