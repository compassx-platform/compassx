"""Fernet encryption for ingestion secrets. Same fallback as the connection service."""
from __future__ import annotations

import base64
import os


def _get_fernet():
    """Return a Fernet instance keyed from INGESTION_SECRET_KEY env var."""
    try:
        from cryptography.fernet import Fernet
        key = os.environ.get("INGESTION_SECRET_KEY", "")
        if not key:
            # Generate a stable key from a fallback passphrase — NOT for prod.
            import hashlib
            raw = hashlib.sha256(b"compassx-ingestion-dev-key-v1").digest()
            key = base64.urlsafe_b64encode(raw).decode()
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ImportError:
        return None


def _encrypt(value: str) -> bytes:
    f = _get_fernet()
    if f:
        return f.encrypt(value.encode())
    # Fallback: base64 obfuscation (not secure — use cryptography pkg in prod)
    return base64.b64encode(value.encode())


def _decrypt(data: bytes) -> str:
    f = _get_fernet()
    if f:
        return f.decrypt(data).decode()
    return base64.b64decode(data).decode()
