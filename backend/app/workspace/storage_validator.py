"""Storage config validation and credential encryption.

Validates storage credentials by attempting a test blob write.
Encrypts sensitive fields using Fernet (reuses catalog_fernet_key from settings).
"""
from __future__ import annotations

import json
import logging

from cryptography.fernet import Fernet

from app.config import settings

logger = logging.getLogger(__name__)

_SENSITIVE_FIELDS = frozenset(["account_key", "access_key", "secret_key", "password"])


def _fernet() -> Fernet:
    return Fernet(settings.catalog_fernet_key)


def validate_storage_config(backend: str, config: dict) -> None:
    """Attempt a test write to verify credentials. Raises ValueError on failure."""
    try:
        if backend == "minio":
            _test_minio(config)
        elif backend == "s3":
            _test_s3(config)
        elif backend == "azure":
            _test_azure(config)
        else:
            raise ValueError(f"Unknown storage backend: {backend!r}")
    except Exception as exc:
        raise ValueError(f"Storage config validation failed: {exc}") from exc


def _test_minio(config: dict) -> None:
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=config["endpoint"],
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"],
        config=Config(connect_timeout=5, read_timeout=5),
    )
    bucket = config["bucket"]
    prefix = config.get("prefix", "")
    test_key = f"{prefix}.compassx_probe"
    s3.put_object(Bucket=bucket, Key=test_key, Body=b"probe")
    s3.delete_object(Bucket=bucket, Key=test_key)


def _test_s3(config: dict) -> None:
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        region_name=config["region"],
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"],
        config=Config(connect_timeout=5, read_timeout=5),
    )
    bucket = config["bucket"]
    prefix = config.get("prefix", "")
    test_key = f"{prefix}.compassx_probe"
    s3.put_object(Bucket=bucket, Key=test_key, Body=b"probe")
    s3.delete_object(Bucket=bucket, Key=test_key)


def _test_azure(config: dict) -> None:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient(
        account_url=f"https://{config['account_name']}.blob.core.windows.net",
        credential=config["account_key"],
    )
    container = config["container"]
    prefix = config.get("prefix", "")
    test_blob = f"{prefix}.compassx_probe"
    blob_client = client.get_blob_client(container=container, blob=test_blob)
    blob_client.upload_blob(b"probe", overwrite=True)
    blob_client.delete_blob()


def encrypt_storage_config(config: dict) -> dict:
    """Return a copy with sensitive fields encrypted."""
    f = _fernet()
    result = {}
    for k, v in config.items():
        if k in _SENSITIVE_FIELDS and isinstance(v, str):
            result[k] = f.encrypt(v.encode()).decode()
        else:
            result[k] = v
    return result


def decrypt_storage_config(config: dict) -> dict:
    """Return a copy with sensitive fields decrypted."""
    from app.services.encryption import decrypt_field
    result = {}
    for k, v in config.items():
        if k in _SENSITIVE_FIELDS and isinstance(v, str):
            try:
                result[k] = decrypt_field(v)
            except Exception:
                result[k] = v  # not encrypted or already plain
        else:
            result[k] = v
    return result
