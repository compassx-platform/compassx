"""AWS S3 backend implementation using aiobotocore."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiobotocore.session

from .backend import BlobStorageBackend
from .models import FileInfo

logger = logging.getLogger(__name__)


class S3StorageBackend(BlobStorageBackend):
    """AWS S3 backend. Also serves as the base for MinIO via endpoint_url override."""

    def __init__(
        self,
        bucket: str,
        base_path: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str | None = None,
    ):
        self.bucket = bucket
        self.base_path = base_path.rstrip("/") + "/"
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint_url = endpoint_url
        self._session = aiobotocore.session.get_session()

    def _key(self, path: str) -> str:
        return self.base_path + path.lstrip("/")

    def _client_kwargs(self) -> dict:
        kwargs: dict = dict(
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        return kwargs

    async def write_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        async with self._session.create_client("s3", **self._client_kwargs()) as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=self._key(path),
                Body=data,
                ContentType=content_type,
            )

    async def read_bytes(self, path: str) -> bytes:
        async with self._session.create_client("s3", **self._client_kwargs()) as client:
            resp = await client.get_object(Bucket=self.bucket, Key=self._key(path))
            return await resp["Body"].read()

    async def delete(self, path: str) -> None:
        async with self._session.create_client("s3", **self._client_kwargs()) as client:
            await client.delete_object(Bucket=self.bucket, Key=self._key(path))

    async def list_files(self, prefix: str) -> list[FileInfo]:
        full_prefix = self._key(prefix)
        files: list[FileInfo] = []
        async with self._session.create_client("s3", **self._client_kwargs()) as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
                for obj in page.get("Contents", []):
                    relative = obj["Key"].removeprefix(self.base_path)
                    files.append(FileInfo(
                        file_path=relative,
                        file_name=relative.split("/")[-1],
                        size_bytes=obj["Size"],
                        content_type=None,
                        last_modified=obj["LastModified"],
                    ))
        return files

    async def exists(self, path: str) -> bool:
        async with self._session.create_client("s3", **self._client_kwargs()) as client:
            try:
                await client.head_object(Bucket=self.bucket, Key=self._key(path))
                return True
            except Exception:
                return False

    async def get_url(self, path: str, expiry_seconds: int = 3600) -> str:
        async with self._session.create_client("s3", **self._client_kwargs()) as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": self._key(path)},
                ExpiresIn=expiry_seconds,
            )

    async def mint_scoped_credential(
        self,
        prefix: str,
        mode: str = "read",
        ttl_seconds: int = 900,
    ) -> dict:
        """Mint STS temporary credentials scoped to a blob prefix with mode-specific permissions."""
        if mode not in ("read", "write", "readwrite"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'read', 'write', or 'readwrite'.")

        # Build policy statements based on mode
        statements = []

        # Object-level permissions
        actions = []
        if mode in ("read", "readwrite"):
            actions.append("s3:GetObject")
        if mode in ("write", "readwrite"):
            actions.extend(["s3:PutObject", "s3:DeleteObject"])

        if actions:
            statements.append({
                "Effect": "Allow",
                "Action": actions,
                "Resource": f"arn:aws:s3:::{self.bucket}/{prefix}*",
            })

        # ListBucket permission for read modes
        if mode in ("read", "readwrite"):
            statements.append({
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": f"arn:aws:s3:::{self.bucket}",
                "Condition": {
                    "StringLike": {
                        "s3:prefix": f"{prefix}*",
                    },
                },
            })

        policy = {
            "Version": "2012-10-17",
            "Statement": statements,
        }

        import json
        async with self._session.create_client("sts", **self._client_kwargs()) as sts:
            resp = await sts.assume_role(
                RoleArn=f"arn:aws:iam::123456789012:role/CompassXNotebookAccess",  # Placeholder
                RoleSessionName="compassx-notebook-session",
                DurationSeconds=ttl_seconds,
                Policy=json.dumps(policy),
            )
            creds = resp["Credentials"]
            return {
                "backend_type": "s3",
                "container": self.bucket,
                "prefix": prefix,
                "scoped_credential": {
                    "access_key": creds["AccessKeyId"],
                    "secret_key": creds["SecretAccessKey"],
                    "session_token": creds["SessionToken"],
                    "endpoint_url": self.endpoint_url,
                },
                "expires_at": creds["Expiration"].isoformat(),
            }
