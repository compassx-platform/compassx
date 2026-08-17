"""Abstract base class for all blob storage backends."""
from abc import ABC, abstractmethod

from .models import FileInfo


class BlobStorageBackend(ABC):
    """
    All operations are async.
    Paths are always relative to the backend's configured base_path.
    The backend prepends base_path internally.
    """

    @abstractmethod
    async def write_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Write bytes to the given relative path, overwriting if it exists."""
        ...

    @abstractmethod
    async def read_bytes(self, path: str) -> bytes:
        """Read all bytes from the given relative path."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete the blob at the given relative path."""
        ...

    @abstractmethod
    async def list_files(self, prefix: str) -> list[FileInfo]:
        """List all blobs whose paths start with prefix."""
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Return True if a blob exists at the given relative path."""
        ...

    @abstractmethod
    async def get_url(self, path: str, expiry_seconds: int = 3600) -> str:
        """Return a presigned/SAS URL for temporary direct access."""
        ...

    @abstractmethod
    async def mint_scoped_credential(
        self,
        prefix: str,
        mode: str = "read",
        ttl_seconds: int = 900,
    ) -> dict:
        """
        Mint scoped credential for a blob prefix.
        Used by volume access to provide credentials to notebook kernels.

        Args:
            prefix: Blob storage prefix (e.g., "catalog/schema/volumes/name/")
            mode: Access mode: "read", "write", or "readwrite"
            ttl_seconds: Credential time-to-live in seconds (default 15 min)

        Returns:
            Backend-specific dict with:
            - backend_type: "azure" | "s3" | "minio"
            - container: Container/bucket name
            - prefix: The prefix these credentials are scoped to
            - scoped_credential: Backend-specific credential data (SAS token, STS creds, etc.)
            - expires_at: ISO8601 timestamp when credential expires
        """
        ...
