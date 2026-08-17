"""CompassX fsspec protocol for volume access via cx:// URLs.

This module registers the cx:// protocol handler for notebook kernels,
enabling pandas, PyArrow, and other data libraries to read from CompassX volumes.

Example:
    import pandas as pd
    df = pd.read_csv("cx://catalog.schema.volume/path/to/file.csv")

Environment variables required:
    NOTEBOOK_SESSION_TOKEN: JWT token for catalog API authentication
    CATALOG_API_URL: Base URL for catalog API (e.g., http://localhost:5000/api/v1)
"""
import logging
import ssl

# Bypass SSL certificate verification globally to resolve corporate proxy SSL interception
ssl._create_default_https_context = ssl._create_unverified_context

# Disable insecure request warnings
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

# Patch synchronous Azure transport
try:
    from azure.core.pipeline.transport import RequestsTransport
    _orig_requests_send = RequestsTransport.send
    def _patched_requests_send(self, request, **kwargs):
        kwargs["connection_verify"] = False
        return _orig_requests_send(self, request, **kwargs)
    RequestsTransport.send = _patched_requests_send
except ImportError:
    pass

# Patch asynchronous Azure transport
try:
    from azure.core.pipeline.transport import AioHttpTransport
    _orig_aiohttp_send = AioHttpTransport.send
    async def _patched_aiohttp_send(self, request, **kwargs):
        kwargs["connection_verify"] = False
        return await _orig_aiohttp_send(self, request, **kwargs)
    AioHttpTransport.send = _patched_aiohttp_send
except ImportError:
    pass

logger = logging.getLogger(__name__)

try:
    import fsspec
    from .cx_protocol import CXFileSystem

    fsspec.register_implementation("cx", CXFileSystem)
    logger.debug("Registered cx:// protocol with fsspec")
except ImportError:
    logger.warning("fsspec not available - cx:// protocol registration skipped")
except Exception as exc:
    logger.error("Failed to register cx:// protocol: %s", exc)

__all__ = ["CXFileSystem"]
