"""Storage resolver module.

Resolves workspace storage configuration:
- For managed workspaces (storage_backend="managed" or empty config), inherits account-level
  default storage (MinIO/S3/Azure/local) configured via environment / docker compose and isolates
  workspace data under `workspaces/{slug}/`.
- For custom workspaces, decrypts and returns custom credentials.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.workspace.storage_validator import decrypt_storage_config

if TYPE_CHECKING:
    from app.workspace.models import Workspace

logger = logging.getLogger(__name__)


def _build_prefix(base_prefix: str, workspace_slug: str | None = None) -> str:
    parts = []
    if base_prefix:
        parts.append(base_prefix.strip("/"))
    if workspace_slug:
        parts.append(f"workspaces/{workspace_slug}")
    if not parts:
        return ""
    return "/".join(parts) + "/"


def get_managed_storage_config(workspace_slug: str | None = None) -> tuple[str, dict[str, Any]]:
    """Return the (backend, config_dict) for account-level managed storage."""
    backend = (settings.STORAGE_BACKEND or "minio").lower()
    prefix = _build_prefix(settings.STORAGE_PREFIX, workspace_slug)

    if backend == "minio":
        return "minio", {
            "endpoint": settings.STORAGE_ENDPOINT,
            "bucket": settings.STORAGE_BUCKET,
            "access_key": settings.STORAGE_ACCESS_KEY,
            "secret_key": settings.STORAGE_SECRET_KEY,
            "region": settings.STORAGE_REGION,
            "prefix": prefix,
        }
    elif backend == "s3":
        return "s3", {
            "bucket": settings.STORAGE_BUCKET,
            "region": settings.STORAGE_REGION,
            "access_key": settings.STORAGE_ACCESS_KEY,
            "secret_key": settings.STORAGE_SECRET_KEY,
            "prefix": prefix,
        }
    elif backend == "azure":
        return "azure", {
            "account_name": settings.STORAGE_ACCESS_KEY,
            "account_key": settings.STORAGE_SECRET_KEY,
            "container": settings.STORAGE_BUCKET,
            "prefix": prefix,
        }
    else:
        return "local", {
            "prefix": prefix,
        }


def resolve_workspace_storage(workspace: Any) -> tuple[str, dict[str, Any]]:
    """Resolve effective (backend, config) for a given Workspace model instance.
    
    If workspace.storage_backend is 'managed' or empty/unconfigured, returns account-level managed storage.
    Otherwise, returns decrypted custom workspace storage.
    """
    if workspace is None:
        return get_managed_storage_config()

    backend = getattr(workspace, "storage_backend", None) or "managed"
    storage_config = getattr(workspace, "storage_config", None) or {}

    # If workspace is configured as managed or storage_config is empty, inherit managed storage
    if backend in ("managed", "default") or not storage_config:
        slug = getattr(workspace, "slug", None)
        return get_managed_storage_config(slug)

    # Custom storage configured on workspace
    return backend, decrypt_storage_config(storage_config)


def ensure_default_storage_bucket() -> None:
    """Probes and ensures the default bucket / container exists if using MinIO or S3."""
    backend = (settings.STORAGE_BACKEND or "minio").lower()
    bucket = settings.STORAGE_BUCKET

    if backend in ("minio", "s3"):
        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import ClientError

            kwargs: dict[str, Any] = {
                "aws_access_key_id": settings.STORAGE_ACCESS_KEY,
                "aws_secret_access_key": settings.STORAGE_SECRET_KEY,
                "config": Config(connect_timeout=3, read_timeout=3),
            }
            if backend == "minio":
                kwargs["endpoint_url"] = settings.STORAGE_ENDPOINT
            if settings.STORAGE_REGION:
                kwargs["region_name"] = settings.STORAGE_REGION

            s3 = boto3.client("s3", **kwargs)
            try:
                s3.head_bucket(Bucket=bucket)
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code", "")
                if error_code in ("404", "NoSuchBucket"):
                    logger.info("Default storage bucket '%s' does not exist. Creating...", bucket)
                    if settings.STORAGE_REGION and settings.STORAGE_REGION != "us-east-1" and backend != "minio":
                        s3.create_bucket(
                            Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": settings.STORAGE_REGION},
                        )
                    else:
                        s3.create_bucket(Bucket=bucket)
                    logger.info("Default storage bucket '%s' created successfully.", bucket)
                else:
                    logger.warning("Could not head default bucket '%s': %s", bucket, exc)
        except Exception as err:
            logger.warning("Could not ensure default storage bucket '%s': %s", bucket, err)
