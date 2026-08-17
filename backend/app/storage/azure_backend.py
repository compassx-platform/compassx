"""Azure Blob Storage / ADLS Gen2 backend implementation."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from azure.identity.aio import ClientSecretCredential
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions, generate_container_sas, ContainerSasPermissions

from .backend import BlobStorageBackend
from .models import FileInfo

logger = logging.getLogger(__name__)


class AzureStorageBackend(BlobStorageBackend):
    """Azure Blob Storage backend. Supports account-key auth and service-principal auth."""

    def __init__(
        self,
        account_name: str,
        container: str,
        base_path: str,
        account_key: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        self.account_name = account_name
        self.container = container
        self.base_path = base_path.rstrip("/") + "/"
        self.account_key = account_key
        self._account_url = f"https://{account_name}.blob.core.windows.net"
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        # Lazily created inside the running event loop to avoid "Future attached to
        # a different loop" errors when the backend is constructed at import/config time.
        self._client: BlobServiceClient | None = None

    def _get_client(self) -> BlobServiceClient:
        """Return (or create) BlobServiceClient bound to the current event loop."""
        if self._client is None:
            if self.account_key:
                self._client = BlobServiceClient(
                    account_url=self._account_url, credential=self.account_key
                )
            else:
                credential = ClientSecretCredential(
                    self._tenant_id, self._client_id, self._client_secret
                )
                self._client = BlobServiceClient(
                    account_url=self._account_url, credential=credential
                )
        return self._client

    def _blob_path(self, path: str) -> str:
        return self.base_path + path.lstrip("/")

    async def write_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        blob_name = self._blob_path(path)
        logger.info(
            "AzureBackend.write_bytes  container=%r  blob=%r  content_type=%r  base_path=%r  raw_path=%r",
            self.container, blob_name, content_type, self.base_path, path,
        )
        from azure.storage.blob import ContentSettings
        from azure.core.exceptions import ResourceNotFoundError
        
        blob_client = self._get_client().get_blob_client(self.container, blob_name)
        try:
            await blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        except ResourceNotFoundError as e:
            if "ContainerNotFound" in str(e):
                logger.info("Container %r not found, creating it...", self.container)
                container_client = self._get_client().get_container_client(self.container)
                await container_client.create_container()
                await blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type=content_type),
                )
            else:
                raise



    async def read_bytes(self, path: str) -> bytes:
        blob_client = self._get_client().get_blob_client(self.container, self._blob_path(path))
        stream = await blob_client.download_blob()
        return await stream.readall()

    async def delete(self, path: str) -> None:
        blob_client = self._get_client().get_blob_client(self.container, self._blob_path(path))
        await blob_client.delete_blob()

    async def list_files(self, prefix: str) -> list[FileInfo]:
        full_prefix = self._blob_path(prefix)
        container_client: ContainerClient = self._get_client().get_container_client(self.container)
        files: list[FileInfo] = []
        async for blob in container_client.list_blobs(name_starts_with=full_prefix):
            relative = blob.name.removeprefix(self.base_path)
            ct = None
            if blob.content_settings and hasattr(blob.content_settings, "content_type"):
                ct = blob.content_settings.content_type
            files.append(FileInfo(
                file_path=relative,
                file_name=relative.split("/")[-1],
                size_bytes=blob.size or 0,
                content_type=ct,
                last_modified=blob.last_modified or datetime.now(timezone.utc),
            ))
        return files

    async def exists(self, path: str) -> bool:
        blob_client = self._get_client().get_blob_client(self.container, self._blob_path(path))
        return await blob_client.exists()

    async def get_url(self, path: str, expiry_seconds: int = 3600) -> str:
        if not self.account_key:
            raise ValueError(
                "Presigned URL generation requires account_key auth. "
                "Service principal auth does not support SAS token generation from client side."
            )
        expiry = datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds)
        blob_name = self._blob_path(path)
        sas = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )
        return f"https://{self.account_name}.blob.core.windows.net/{self.container}/{blob_name}?{sas}"

    async def mint_scoped_credential(
        self,
        prefix: str,
        mode: str = "read",
        ttl_seconds: int = 900,
    ) -> dict:
        """Mint SAS token scoped to a blob prefix with mode-specific permissions."""
        if not self.account_key:
            raise ValueError(
                "Scoped credential minting requires account_key auth. "
                "Service principal auth does not support SAS token generation from client side."
            )
        if mode not in ("read", "write", "readwrite"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'read', 'write', or 'readwrite'.")

        expiry = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        # Map mode to SAS permissions
        if mode == "read":
            perms = ContainerSasPermissions(read=True, list=True)
        elif mode == "write":
            perms = ContainerSasPermissions(add=True, create=True, write=True, delete=True)
        else:  # readwrite
            perms = ContainerSasPermissions(read=True, add=True, create=True, write=True, delete=True, list=True)

        sas = generate_container_sas(
            account_name=self.account_name,
            container_name=self.container,
            account_key=self.account_key,
            permission=perms,
            expiry=expiry,
        )
        return {
            "backend_type": "azure",
            "container": self.container,
            "prefix": prefix,
            "scoped_credential": {
                "sas_token": sas,
                "account_name": self.account_name,
            },
            "expires_at": expiry.isoformat(),
        }
