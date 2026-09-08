"""fsspec protocol handler for cx:// volume access."""
import logging
import os
from typing import Optional

from fsspec.spec import AbstractFileSystem
from fsspec.utils import infer_storage_options

from .credential_cache import CredentialCache

logger = logging.getLogger(__name__)


def _fsspec_mode_to_cx_mode(mode: str) -> str:
    """Map fsspec mode string to cx mode for credential resolution.

    Args:
        mode: fsspec mode string (e.g., 'rb', 'wb', 'r+b')

    Returns:
        cx mode: 'read', 'write', or 'readwrite'
    """
    if "+" in mode:
        return "readwrite"
    elif "w" in mode or "a" in mode:
        return "write"
    else:
        return "read"


class CXFileWrapper:
    """Wrapper around fsspec backend file objects to notify host of file writes."""
    def __init__(self, raw_file, catalog: str, schema: str, volume: str, file_path: str, fs_instance):
        self.raw_file = raw_file
        self.catalog = catalog
        self.schema = schema
        self.volume = volume
        self.file_path = file_path
        self.fs_instance = fs_instance

    def __getattr__(self, name):
        return getattr(self.raw_file, name)

    def __enter__(self):
        self.raw_file.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        res = self.raw_file.__exit__(exc_type, exc_val, exc_tb)
        if exc_type is None:
            self.close()
        return res

    def __iter__(self):
        return iter(self.raw_file)

    def __next__(self):
        return next(self.raw_file)

    def close(self):
        self.raw_file.close()
        try:
            self.fs_instance._notify_backend_write(
                self.catalog, self.schema, self.volume, self.file_path
            )
        except Exception as e:
            logger.warning("CXFileWrapper close notification failed: %s", e)


class CXFileSystem(AbstractFileSystem):
    """fsspec handler for cx://catalog.schema.volume/path/to/file protocol.

    Usage:
        import fsspec
        import pandas as pd

        # fsspec automatically registers cx:// via entry point
        df = pd.read_csv("cx://compassx.scada.raw_files/data.csv")

    Environment variables:
        NOTEBOOK_SESSION_TOKEN: JWT token for catalog API auth
        CATALOG_API_URL: Base URL for catalog API (e.g., http://localhost:5000/api/v1)
    """

    protocol = "cx"
    root_marker = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cache = CredentialCache()

        # Initialize from environment
        session_token = (
            os.environ.get("NOTEBOOK_SESSION_TOKEN")
            or os.environ.get("KERNEL_NOTEBOOK_SESSION_TOKEN")
            or os.environ.get("JUPYTER_TOKEN")
        )
        catalog_url = os.environ.get("KERNEL_CATALOG_API_URL") or os.environ.get("CATALOG_API_URL")
        if catalog_url and catalog_url.startswith(("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
            from compassx.lookup import try_resolve_url_container
            catalog_url = try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"

        if not session_token or not catalog_url:
            logger.warning(
                "CX filesystem: missing env vars - NOTEBOOK_SESSION_TOKEN=%s, CATALOG_API_URL=%s",
                bool(session_token),
                bool(catalog_url),
            )

        if session_token and catalog_url:
            self._cache.set_session_token(session_token, catalog_url)

    def _parse_path(self, path: str) -> tuple[str, str, str, str]:
        """Parse cx://catalog.schema.volume/path/to/file.

        Returns:
            (catalog, schema, volume, file_path)
        """
        # Remove protocol if present
        if path.startswith("cx://"):
            path = path[5:]
        # Remove leading slashes
        path = path.lstrip("/")

        # Split on first slash to separate volume ref from file path
        if "/" in path:
            volume_ref, file_path = path.split("/", 1)
        else:
            volume_ref = path
            file_path = ""

        # Parse volume ref: catalog.schema.volume
        parts = volume_ref.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid cx:// path format: {path!r}. "
                f"Expected: cx://catalog.schema.volume/path/to/file"
            )

        catalog, schema, volume = parts
        return catalog, schema, volume, file_path

    def _build_backend_fs(self, credential: dict) -> AbstractFileSystem:
        """Construct backend fsspec filesystem from credential."""
        backend_type = credential["backend_type"]

        if backend_type == "azure":
            import adlfs

            cred = credential["scoped_credential"]
            return adlfs.AzureBlobFileSystem(
                account_name=cred["account_name"],
                container_name=credential["container"],
                sas_token=cred["sas_token"],
                connection_verify=False,
            )

        elif backend_type in ("s3", "minio"):
            import s3fs

            cred = credential["scoped_credential"]
            endpoint_url = cred.get("endpoint_url")
            if endpoint_url and endpoint_url.startswith(("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
                try:
                    from compassx.lookup import try_resolve_url_container
                    endpoint_url = try_resolve_url_container("minio", endpoint_url)
                except Exception:
                    pass
                if endpoint_url.startswith(("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
                    host_gateway = os.environ.get("COMPASSX_HOST_GATEWAY", "host.docker.internal")
                    endpoint_url = endpoint_url.replace("localhost", host_gateway).replace("127.0.0.1", host_gateway)

            return s3fs.S3FileSystem(
                anon=False,
                key=cred["access_key"],
                secret=cred["secret_key"],
                token=cred.get("session_token"),
                endpoint_url=endpoint_url,
                client_kwargs={"verify": False},
            )

        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

    def _open(self, path: str, mode: str = "rb", **kwargs):
        """Open a file from volume storage.

        Args:
            path: cx://catalog.schema.volume/path/to/file
            mode: File open mode ('rb', 'wb', 'r+b', etc.)
            **kwargs: Passed to backend filesystem

        Returns:
            File-like object
        """
        # Parse path
        catalog, schema, volume, file_path = self._parse_path(path)

        # Detect cx mode from fsspec mode
        cx_mode = _fsspec_mode_to_cx_mode(mode)

        # Resolve credential with mode (cached separately per mode)
        credential = self._cache.get_or_mint(catalog, schema, volume, mode=cx_mode)

        # Construct backend filesystem
        backend_fs = self._build_backend_fs(credential)

        # Build full blob path: prefix + file_path
        prefix = credential["prefix"].rstrip("/")
        blob_path = f"{prefix}/{file_path}".lstrip("/")

        logger.debug(
            "CX open: %s (backend=%s, blob_path=%s)",
            path,
            credential["backend_type"],
            blob_path,
        )

        # Delegate to backend
        raw_file = backend_fs._open(blob_path, mode=mode, **kwargs)

        is_write = any(c in mode for c in ("w", "a", "+"))
        if is_write:
            return CXFileWrapper(raw_file, catalog, schema, volume, file_path, self)

        return raw_file

    def _notify_backend_write(self, catalog: str, schema: str, volume: str, file_path: str):
        """Notify the catalog backend that a file has been written to register/index it."""
        token = self._cache._session_token
        url = self._cache._catalog_url
        if not token or not url:
            logger.debug("CX: Missing session token or catalog URL for notification")
            return

        import httpx
        try:
            record_url = f"{url.rstrip('/')}/volumes/record-file"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "catalog": catalog,
                "schema_name": schema,
                "volume_name": volume,
                "file_path": file_path
            }
            # Make a synchronous request since close is synchronous in fsspec
            # Set verify=False to bypass SSL decryption issues (Minikube / Corporate VPN proxy)
            with httpx.Client(verify=False) as client:
                resp = client.post(record_url, json=payload, headers=headers)
                resp.raise_for_status()
            logger.debug("CX: Registered file write %s.%s.%s/%s", catalog, schema, volume, file_path)
        except Exception as exc:
            logger.warning("CX: Failed to register file write: %s", exc)

    def cat_file(self, path: str, start: Optional[int] = None, end: Optional[int] = None, **kwargs) -> bytes:
        """Read file contents."""
        with self._open(path, "rb", **kwargs) as f:
            if start is not None:
                f.seek(start)
            data = f.read(end - start if end is not None else -1)
        return data

    def ls(self, path: str, detail: bool = False, refresh: bool = False, **kwargs) -> list:
        """List directory contents."""
        catalog, schema, volume, file_path = self._parse_path(path)
        credential = self._cache.get_or_mint(catalog, schema, volume, mode="read")
        backend_fs = self._build_backend_fs(credential)

        prefix = credential["prefix"].rstrip("/")
        blob_path = f"{prefix}/{file_path}".lstrip("/")

        try:
            return backend_fs.ls(blob_path, detail=detail, refresh=refresh, **kwargs)
        except FileNotFoundError:
            return []

    def exists(self, path: str, **kwargs) -> bool:
        """Check if file exists."""
        try:
            catalog, schema, volume, file_path = self._parse_path(path)
            credential = self._cache.get_or_mint(catalog, schema, volume, mode="read")
            backend_fs = self._build_backend_fs(credential)

            prefix = credential["prefix"].rstrip("/")
            blob_path = f"{prefix}/{file_path}".lstrip("/")

            return backend_fs.exists(blob_path, **kwargs)
        except Exception as exc:
            logger.debug("CX exists check failed: %s", exc)
            return False
