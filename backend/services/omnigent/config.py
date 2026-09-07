"""Omnigent platform service configuration."""
import os
from pydantic_settings import BaseSettings


class OmnigentSettings(BaseSettings):
    OMNIGENT_PORT: int = int(os.getenv("OMNIGENT_PORT", "6767"))
    OMNIGENT_HOST: str = os.getenv("OMNIGENT_HOST", "0.0.0.0")
    OMNIGENT_CONTAINER_NAME: str = os.getenv("OMNIGENT_CONTAINER_NAME", "compassx-omnigent-server")
    OMNIGENT_IMAGE: str = os.getenv("OMNIGENT_IMAGE", "ghcr.io/omnigent-ai/omnigent-server:latest")
    OMNIGENT_VOLUME_NAME: str = os.getenv("OMNIGENT_VOLUME_NAME", "compassx-omnigent-data")
    OMNIGENT_SERVER_URL: str = os.getenv("OMNIGENT_SERVER_URL", "http://localhost:6767")
    OMNIGENT_INTERNAL_URL: str = os.getenv("OMNIGENT_INTERNAL_URL", "http://compassx-omnigent-server:6767")

    class Config:
        env_prefix = ""
        case_sensitive = True


omnigent_settings = OmnigentSettings()
