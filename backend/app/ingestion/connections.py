"""
Connection service layer — CRUD for ingestion_connection and credential_secret.

Security rules (from spec D9):
  - Credentials are resolved server-side at execution time only.
  - Raw secret values are never returned, stored in plaintext, or logged.
  - The GET response contains `has_secret=True/False`, not the secret itself.
"""
from __future__ import annotations

import base64
import os
import uuid
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionConnection, CredentialSecret

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Minimal symmetric encryption for secrets at rest.
# Production deployments should swap this for a proper KMS-backed solution.
# We use Fernet (symmetric AES-128-CBC + HMAC) from the cryptography package.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def create_connection(
    db: Session,
    workspace_id: UUID,
    name: str,
    base_url: str,
    auth_type: str,
    auth_config: dict,
    secret_value: Optional[str],
    default_headers: dict,
    rate_limit_rps: float,
    max_concurrency: int,
    created_by: UUID,
    description: Optional[str] = None,
) -> IngestionConnection:
    """Create a new Connection, storing any secret encrypted in credential_secret."""

    secret_ref = None
    if secret_value:
        secret = CredentialSecret(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            encrypted_value=_encrypt(secret_value),
            encryption_key_version=1,
        )
        db.add(secret)
        db.flush()
        secret_ref = secret.id

    conn = IngestionConnection(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        name=name,
        description=description,
        base_url=base_url,
        auth_type=auth_type,
        auth_config=auth_config,
        secret_ref=secret_ref,
        default_headers=default_headers,
        rate_limit_rps=rate_limit_rps,
        max_concurrency=max_concurrency,
        created_by=created_by,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def get_connection(
    db: Session, workspace_id: UUID, connection_id: UUID
) -> IngestionConnection:
    conn = (
        db.query(IngestionConnection)
        .filter(
            IngestionConnection.id == connection_id,
            IngestionConnection.workspace_id == workspace_id,
        )
        .first()
    )
    if not conn:
        raise ValueError(f"Connection {connection_id} not found")
    return conn


def list_connections(db: Session, workspace_id: UUID) -> List[IngestionConnection]:
    return (
        db.query(IngestionConnection)
        .filter(IngestionConnection.workspace_id == workspace_id)
        .order_by(IngestionConnection.name)
        .all()
    )


def update_connection(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
    **fields,
) -> IngestionConnection:
    conn = get_connection(db, workspace_id, connection_id)
    for key, value in fields.items():
        if value is not None and hasattr(conn, key):
            setattr(conn, key, value)
    db.commit()
    db.refresh(conn)
    return conn


def rotate_connection_secret(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
    new_secret_value: str,
) -> None:
    """Replace (or create) the credential_secret for this connection."""
    conn = get_connection(db, workspace_id, connection_id)

    if conn.secret_ref:
        # Update existing secret row
        secret = db.query(CredentialSecret).filter(
            CredentialSecret.id == conn.secret_ref
        ).first()
        if secret:
            secret.encrypted_value = _encrypt(new_secret_value)
            secret.encryption_key_version = 1
        else:
            # orphaned ref — create fresh
            secret = CredentialSecret(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                encrypted_value=_encrypt(new_secret_value),
                encryption_key_version=1,
            )
            db.add(secret)
            db.flush()
            conn.secret_ref = secret.id
    else:
        secret = CredentialSecret(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            encrypted_value=_encrypt(new_secret_value),
            encryption_key_version=1,
        )
        db.add(secret)
        db.flush()
        conn.secret_ref = secret.id

    db.commit()


def delete_connection(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
) -> None:
    """Delete a connection. Blocked if any *enabled* job configs reference it."""
    from app.ingestion.models import IngestionJobConfig

    enabled_count = (
        db.query(IngestionJobConfig)
        .filter(
            IngestionJobConfig.connection_id == connection_id,
            IngestionJobConfig.workspace_id == workspace_id,
            IngestionJobConfig.is_enabled == True,  # noqa: E712
        )
        .count()
    )
    if enabled_count > 0:
        raise ValueError(
            f"Cannot delete connection — {enabled_count} enabled job config(s) still reference it. "
            "Disable them first."
        )

    conn = get_connection(db, workspace_id, connection_id)
    db.delete(conn)
    db.commit()


def resolve_secret(db: Session, connection: IngestionConnection) -> Optional[str]:
    """Decrypt and return the raw secret for a connection. Server-side only."""
    if not connection.secret_ref:
        return None
    secret = db.query(CredentialSecret).filter(
        CredentialSecret.id == connection.secret_ref
    ).first()
    if not secret:
        return None
    return _decrypt(secret.encrypted_value)
