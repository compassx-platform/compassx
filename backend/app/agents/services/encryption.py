"""Fernet encryption helpers for storing sensitive credentials.

Reuses the catalog_fernet_key already established in app.config — so
LLM API keys and DB passwords are encrypted with the same key as data
catalog connection strings.

Usage:
    from app.services.encryption import encrypt_field, decrypt_field

    stored = encrypt_field("my-secret-api-key")   # store in DB
    original = decrypt_field(stored)              # retrieve
"""

from __future__ import annotations

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    return Fernet(settings.catalog_fernet_key)


def encrypt_field(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns a URL-safe base64 token."""
    if not plaintext:
        return plaintext
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_field(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    if not token:
        return token
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception) as exc:
        # Try fallbacks for dev db names (idcc_core, test, etc.)
        import hashlib
        import base64
        from cryptography.fernet import Fernet
        
        fallback_seeds = [
            "idcc_core",
            "test",
            "compassx_account",
            "compassx_system",
            "landing_zone",
            "postgres",
        ]
        for db_name in fallback_seeds:
            try:
                seed = f"{settings.PG_PASSWORD}:{db_name}:catalog-key-v1"
                digest = hashlib.sha256(seed.encode()).digest()
                key = base64.urlsafe_b64encode(digest)
                return Fernet(key).decrypt(token.encode()).decode()
            except Exception:
                pass

        raise ValueError("Cannot decrypt stored secret; check CATALOG_ENCRYPTION_KEY") from exc


def mask_key(key: str) -> str:
    """Return a display-safe masked version: 'sk-...abcd' (last 4 chars)."""
    if not key or len(key) < 8:
        return "***"
    return f"***...{key[-4:]}"
