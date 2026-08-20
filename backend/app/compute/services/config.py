"""Compute module configuration - extends app-level settings."""
import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ComputeSettings(BaseSettings):
    """Compute-specific environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    COMPASSX_ENV: str = "local"
    COMPASSX_PLATFORM_ENABLED: bool = True
    # Backend process placement:
    # - host: run backend on localhost (local development)
    # - pod: provision and run backend inside Kubernetes for pod-based testing
    # If unset, the runtime is auto-detected from the execution environment.
    COMPASSX_BACKEND_RUNTIME: str = ""
    COMPASSX_NAMESPACE: str = "compassx"
    POD_CLEANUP_TTL_SECONDS: int = 3600
    MAX_JOBS_PER_USER: int = 3
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    DEFAULT_COMPUTE_ENABLED: bool = False
    DEFAULT_COMPUTE_USER_ID: str = ""
    DEFAULT_COMPUTE_CREATED_BY: str = "system"
    DEFAULT_COMPUTE_NAME: str = "Default Compute"
    DEFAULT_COMPUTE_RUNTIME: str = "duckdb"
    DEFAULT_COMPUTE_PROFILE: str = "local"
    # TODO: TESTING ONLY - Remove after local development. Set to "" for production.
    INSECURE_REGISTRIES: str = "registry-1.docker.io"
    COMPUTE_REGISTRY_PREFIX: str = ""
    SKIP_K8S_SSL_VERIFY: bool = False
    LOCAL_K8S_BOOTSTRAP_ENABLED: bool = False

    def is_local(self) -> bool:
        return self.COMPASSX_ENV == "local"

    def is_k8s(self) -> bool:
        return not self.is_local()

    def resolved_backend_runtime(self) -> str:
        """Return the effective backend runtime mode.

        In Kubernetes, default to 'pod' even when COMPASSX_BACKEND_RUNTIME is not
        explicitly set in the environment. This keeps local development on 'host'
        while allowing in-cluster deployments to work without extra config.
        """
        raw = self.COMPASSX_BACKEND_RUNTIME.strip().lower()
        if raw:
            return raw
        env_raw = os.environ.get("COMPASSX_BACKEND_RUNTIME", "").strip().lower()
        if env_raw:
            return env_raw
        return "pod" if self.is_k8s() else "host"

    def backend_runtime_is_pod(self) -> bool:
        return self.resolved_backend_runtime() == "pod"

    def backend_runtime_is_host(self) -> bool:
        return not self.backend_runtime_is_pod()

    def resolved_default_compute_profile(self) -> str:
        """Return a startup-safe default profile for the active environment."""
        if self.is_k8s() and self.DEFAULT_COMPUTE_PROFILE == "local":
            return "cloud-xs"
        return self.DEFAULT_COMPUTE_PROFILE


compute_settings = ComputeSettings()
