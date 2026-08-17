"""Enterprise Gateway service configuration."""
from compute.config import compute_settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class EGSettings(BaseSettings):
    """EG-specific environment variables. Extends compute settings pattern."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    EG_IMAGE: str = "compassx-enterprise-gateway:latest"
    EG_PORT: int = 8888
    EG_NAMESPACE: str = compute_settings.COMPASSX_NAMESPACE
    KERNEL_NAMESPACE: str = compute_settings.COMPASSX_NAMESPACE
    EG_KERNEL_LAUNCH_TIMEOUT: int = 120
    EG_CONNECTION_FILE_PATH: str = "/tmp"
    JUPYTER_SERVER_IMAGE: str = "quay.io/jupyter/base-notebook:latest"
    JUPYTER_SERVER_PORT: int = 8889
    EG_INTERNAL_URL: str = ""
    JUPYTER_BASE_URL: str = ""
    JUPYTER_WS_URL: str = ""

    def internal_url(self) -> str:
        if self.EG_INTERNAL_URL:
            return self.EG_INTERNAL_URL.rstrip("/")
        from compassx.lookup import try_resolve_url

        return try_resolve_url(
            "enterprise-gateway", f"http://127.0.0.1:{self.EG_PORT}"
        )

    def notebook_base_url(self) -> str:
        if self.JUPYTER_BASE_URL:
            return self.JUPYTER_BASE_URL.rstrip("/")
        from compassx.lookup import try_resolve_url

        # Local mode serves notebooks via the frontend dev server.
        if compute_settings.is_local():
            return try_resolve_url("frontend", "http://localhost:5173")
        return try_resolve_url(
            "jupyter-server",
            f"http://compassx-jupyter-server.{self.EG_NAMESPACE}.svc.cluster.local:{self.JUPYTER_SERVER_PORT}",
        )

    def notebook_ws_url(self) -> str:
        if self.JUPYTER_WS_URL:
            return self.JUPYTER_WS_URL.rstrip("/")
        from compassx.lookup import try_resolve_url

        if compute_settings.is_local():
            return try_resolve_url("frontend", "ws://localhost:5173", protocol="ws")
        return try_resolve_url(
            "jupyter-server",
            f"ws://compassx-jupyter-server.{self.EG_NAMESPACE}.svc.cluster.local:{self.JUPYTER_SERVER_PORT}",
            protocol="ws",
        )


eg_settings = EGSettings()

# Label key used on compute pods - must match runtimes.py _standard_labels
JOB_ID_LABEL = "compassx/job"




