"""Tiny storage abstraction used by DAG generation and notebook output uploads."""
from __future__ import annotations

from pathlib import Path

from services.storage.config import storage_settings


def get_fs(backend: str | None = None):
    backend = (backend or storage_settings.STORAGE_BACKEND).lower()
    if backend == "azure":
        return AzureBlobFS()
    return MinioFS()


class MinioFS:
    backend = "minio"

    def _client(self):
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=storage_settings.minio_endpoint_for_app(),
            aws_access_key_id=storage_settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=storage_settings.MINIO_SECRET_KEY,
            region_name=storage_settings.MINIO_REGION,
        )

    def ensure_bucket(self, bucket: str) -> None:
        client = self._client()
        buckets = {item["Name"] for item in client.list_buckets().get("Buckets", [])}
        if bucket not in buckets:
            client.create_bucket(Bucket=bucket)

    def write_text(self, bucket: str, key: str, content: str) -> None:
        self.ensure_bucket(bucket)
        self._client().put_object(Bucket=bucket, Key=key, Body=content.encode("utf-8"))

    def delete(self, bucket: str, key: str) -> None:
        self._client().delete_object(Bucket=bucket, Key=key)

    def upload_file(self, local_path: str | Path, bucket: str, key: str) -> str:
        self.ensure_bucket(bucket)
        self._client().upload_file(str(local_path), bucket, key)
        return f"s3://{bucket}/{key}"

    def read_text(self, bucket: str, key: str) -> str:
        response = self._client().get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def exists(self, bucket: str, key: str) -> bool:
        import botocore.exceptions
        try:
            self._client().head_object(Bucket=bucket, Key=key)
            return True
        except botocore.exceptions.ClientError:
            return False

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        """Return all keys under prefix in bucket."""
        self.ensure_bucket(bucket)
        client = self._client()
        keys = []
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys


class AzureBlobFS:
    backend = "azure"

    def _service_client(self):
        from azure.storage.blob import BlobServiceClient

        if storage_settings.AZURE_STORAGE_CONNECTION_STRING:
            return BlobServiceClient.from_connection_string(
                storage_settings.AZURE_STORAGE_CONNECTION_STRING
            )
        if storage_settings.AZURE_STORAGE_ACCOUNT_URL:
            return BlobServiceClient(
                account_url=storage_settings.AZURE_STORAGE_ACCOUNT_URL,
                credential=storage_settings.AZURE_STORAGE_ACCOUNT_KEY,
            )
        if storage_settings.AZURE_STORAGE_ACCOUNT_NAME:
            account_url = (
                f"https://{storage_settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
            )
            return BlobServiceClient(
                account_url=account_url,
                credential=storage_settings.AZURE_STORAGE_ACCOUNT_KEY,
            )
        raise ValueError("Azure storage is selected but no Azure Blob credentials are configured.")

    def ensure_bucket(self, bucket: str) -> None:
        container = self._service_client().get_container_client(bucket)
        try:
            container.create_container()
        except Exception:
            if not container.exists():
                raise

    def write_text(self, bucket: str, key: str, content: str) -> None:
        self.ensure_bucket(bucket)
        blob = self._service_client().get_blob_client(container=bucket, blob=key)
        blob.upload_blob(content.encode("utf-8"), overwrite=True)

    def delete(self, bucket: str, key: str) -> None:
        blob = self._service_client().get_blob_client(container=bucket, blob=key)
        blob.delete_blob(delete_snapshots="include")

    def upload_file(self, local_path: str | Path, bucket: str, key: str) -> str:
        self.ensure_bucket(bucket)
        blob = self._service_client().get_blob_client(container=bucket, blob=key)
        with open(local_path, "rb") as handle:
            blob.upload_blob(handle, overwrite=True)
        account = storage_settings.AZURE_STORAGE_ACCOUNT_NAME or "storage"
        return f"azure://{account}/{bucket}/{key}"

    def read_text(self, bucket: str, key: str) -> str:
        blob = self._service_client().get_blob_client(container=bucket, blob=key)
        return blob.download_blob().readall().decode("utf-8")

    def exists(self, bucket: str, key: str) -> bool:
        blob = self._service_client().get_blob_client(container=bucket, blob=key)
        return blob.exists()

    def list_objects(self, bucket: str, prefix: str = "") -> list[str]:
        """Return all blob names under prefix in container."""
        container = self._service_client().get_container_client(bucket)
        return [blob.name for blob in container.list_blobs(name_starts_with=prefix)]
