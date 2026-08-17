"""Credential scoping service for CompassX Apps (§8).

Mints a short-lived scoped token at pod startup using the per-app
credential grant stored in app_credential_grants.

Uses the same scoped-credential-minting pattern as volumes/job-run tokens.
Scope is per-app — not per-branch or per-pod.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.apps.models.apps import App, AppCredentialGrant

logger = logging.getLogger(__name__)

# Token TTL — pods refresh before expiry on a background loop
_TOKEN_TTL_SECONDS = 900  # 15 minutes


class CredentialService:
    """Mints and manages scoped credentials for app pods."""

    def __init__(self, db: Session):
        self._db = db

    def get_grant(self, app_id: uuid.UUID) -> Optional[AppCredentialGrant]:
        return (
            self._db.query(AppCredentialGrant)
            .filter(AppCredentialGrant.app_id == app_id)
            .one_or_none()
        )

    def upsert_grant(
        self,
        app_id: uuid.UUID,
        catalog_grants: list[dict[str, Any]],
        volume_grants: Optional[list[dict[str, Any]]] = None,
    ) -> AppCredentialGrant:
        """Create or replace the credential grant for an app."""
        existing = self.get_grant(app_id)
        if existing:
            existing.catalog_grants = catalog_grants
            existing.volume_grants = volume_grants or []
            self._db.flush()
            return existing

        grant = AppCredentialGrant(
            app_id=app_id,
            catalog_grants=catalog_grants,
            volume_grants=volume_grants or [],
        )
        self._db.add(grant)
        self._db.flush()
        return grant

    async def mint_scoped_token(self, app_id: uuid.UUID) -> str:
        """Mint a short-lived scoped token for a pod to use at startup.

        Reuses the existing scoped-credential-minting pattern (same mechanism
        as volumes/job-run tokens). The token encodes the catalog + volume
        grants and expires after _TOKEN_TTL_SECONDS.

        Returns an opaque token string to be injected as SCOPED_TOKEN env var.
        """
        grant = self.get_grant(app_id)
        if grant is None:
            logger.warning("No credential grant found for app %s — minting empty-scoped token", app_id)
            catalog_grants: list[dict] = []
            volume_grants: list[dict] = []
        else:
            catalog_grants = grant.catalog_grants or []
            volume_grants = grant.volume_grants or []

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=_TOKEN_TTL_SECONDS)

        # Use the existing workspace scoped-credential infrastructure if available.
        # Falls back to a signed JWT when the workspace token service is not present.
        try:
            from app.workspace.credential_mint import mint_app_token  # type: ignore
            token = await mint_app_token(
                app_id=str(app_id),
                catalog_grants=catalog_grants,
                volume_grants=volume_grants,
                ttl_seconds=_TOKEN_TTL_SECONDS,
            )
            logger.debug("Minted workspace scoped token for app %s (expires %s)", app_id, expires_at)
            return token
        except ImportError:
            pass

        # Fallback: signed JWT (dev / standalone mode)
        import json, hmac, hashlib, base64
        from app.config import settings

        secret = (settings.SECRET_KEY or "dev-secret").encode()
        payload = json.dumps({
            "app_id": str(app_id),
            "catalog_grants": catalog_grants,
            "volume_grants": volume_grants,
            "exp": int(expires_at.timestamp()),
        }, separators=(",", ":")).encode()

        sig = hmac.new(secret, payload, hashlib.sha256).digest()
        token = (
            base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
            + "."
            + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        )
        logger.debug("Minted fallback JWT token for app %s (expires %s)", app_id, expires_at)
        return token
