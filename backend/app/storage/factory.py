"""Factory: builds the correct BlobStorageBackend from a DB row dict."""
from __future__ import annotations

from .backend import BlobStorageBackend
from .azure_backend import AzureStorageBackend
from .s3_backend import S3StorageBackend
from .minio_backend import MinIOStorageBackend
from app.services.encryption import decrypt_field


def build_backend(row: dict) -> BlobStorageBackend:
    """Construct the correct backend from a storage_backends DB row."""
    provider = row["provider"]

    if provider == "azure":
        return AzureStorageBackend(
            account_name=row["azure_account_name"],
            container=row["azure_container"],
            base_path=row.get("azure_base_path") or "compassx/",
            account_key=decrypt_field(row["encrypted_azure_account_key"]) if row.get("encrypted_azure_account_key") else None,
            tenant_id=row.get("azure_tenant_id"),
            client_id=row.get("azure_client_id"),
            client_secret=decrypt_field(row["encrypted_azure_client_secret"]) if row.get("encrypted_azure_client_secret") else None,
        )

    if provider == "s3":
        return S3StorageBackend(
            bucket=row["s3_bucket"],
            base_path=row.get("s3_base_path") or "compassx/",
            region=row.get("s3_region") or "us-east-1",
            access_key=decrypt_field(row["encrypted_access_key"]),
            secret_key=decrypt_field(row["encrypted_secret_key"]),
        )

    if provider == "minio":
        return MinIOStorageBackend(
            bucket=row["s3_bucket"],
            base_path=row.get("s3_base_path") or "compassx/",
            endpoint_url=row["s3_endpoint_url"],
            access_key=decrypt_field(row["encrypted_access_key"]),
            secret_key=decrypt_field(row["encrypted_secret_key"]),
        )

    raise ValueError(f"Unknown storage provider: {provider!r}")
