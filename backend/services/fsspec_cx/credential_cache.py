"""In-process credential cache for volume access."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class CredentialCache:
    """Cache resolved volume credentials with TTL-based expiry."""

    def __init__(self):
        self._cache: dict = {}  # (catalog, schema, volume, mode) -> (credential, expires_at)
        self._session_token: Optional[str] = None
        self._catalog_url: Optional[str] = None

    def set_session_token(self, token: str, catalog_url: str):
        """Set session token and catalog API URL."""
        self._session_token = token
        self._catalog_url = catalog_url

    def _cache_key(self, catalog: str, schema: str, volume: str, mode: str = "read"):
        """Return cache key tuple (includes mode for mode-specific caching)."""
        return (catalog, schema, volume, mode)

    def _is_expired(self, expires_at_str: str) -> bool:
        """Check if credential has expired."""
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        # Refresh if less than 60 seconds remaining
        return now >= expires_at.replace(tzinfo=timezone.utc) - __import__("datetime").timedelta(seconds=60)

    def get_or_mint(
        self,
        catalog: str,
        schema: str,
        volume: str,
        mode: str = "read",
    ) -> dict:
        """Get cached credential or mint new one.

        Args:
            catalog: Catalog name
            schema: Schema name
            volume: Volume name
            mode: Access mode ('read', 'write', or 'readwrite')

        Returns:
            Credential dict with backend_type, container, prefix, scoped_credential, expires_at

        Raises:
            VolumeAccessError: If credential resolution fails
        """
        from .exceptions import map_resolve_error

        if not self._session_token or not self._catalog_url:
            raise RuntimeError("Session token and catalog URL not set - call set_session_token() first")

        key = self._cache_key(catalog, schema, volume, mode)

        # Check cache
        if key in self._cache:
            credential, expires_at = self._cache[key]
            if not self._is_expired(expires_at):
                logger.debug(
                    "Credential cache hit for %s.%s.%s (mode=%s), expires in %s",
                    catalog, schema, volume, mode, expires_at,
                )
                return credential

        # Cache miss or expired - resolve new credential
        logger.debug("Credential cache miss/expired for %s.%s.%s (mode=%s), resolving...", catalog, schema, volume, mode)
        try:
            ws_id = os.environ.get("WORKSPACE_ID") or os.environ.get("KERNEL_WORKSPACE_ID")
            ws_slug = os.environ.get("WORKSPACE_SLUG") or os.environ.get("KERNEL_WORKSPACE_SLUG")

            req_headers = {"Authorization": f"Bearer {self._session_token}"}
            if ws_id:
                req_headers["X-Workspace-Id"] = ws_id
            if ws_slug:
                req_headers["X-Workspace-Slug"] = ws_slug

            req_json = {
                "catalog": catalog,
                "schema_name": schema,
                "volume": volume,
                "mode": mode,
            }
            if ws_id:
                req_json["workspace_id"] = ws_id
            if ws_slug:
                req_json["workspace_slug"] = ws_slug

            resp = httpx.post(
                f"{self._catalog_url}/volumes/resolve",
                headers=req_headers,
                json=req_json,
                timeout=10,
            )
            resp.raise_for_status()
            credential = resp.json()
            self._cache[key] = (credential, credential.get("expires_at"))
            logger.debug("Credential resolved and cached for %s.%s.%s (mode=%s)", catalog, schema, volume, mode)
            return credential
        except httpx.HTTPStatusError as exc:
            try:
                error_data = exc.response.json()
                error_code = error_data.get("error_code", "UNKNOWN")
                error_msg = error_data.get("message", str(exc))
            except Exception:
                error_code = f"HTTP_{exc.response.status_code}"
                error_msg = exc.response.text or str(exc)
            raise map_resolve_error(error_code, error_msg)
        except Exception as exc:
            logger.error("Credential resolve failed: %s", exc)
            raise RuntimeError(f"Failed to resolve volume credentials: {str(exc)}") from exc
