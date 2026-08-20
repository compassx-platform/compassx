"""Service layer for External Connections and encrypted credential handling."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, List, Optional
from sqlalchemy.orm import Session

from app.agents.models.external_connection import ExternalConnection
from app.agents.schemas.external_connections import ExternalConnectionCreate, ExternalConnectionUpdate
from app.agents.services.encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)


def _normalize_auth_config_to_cipher(auth_config: Any) -> Optional[str]:
    """Serialize and Fernet-encrypt auth_config."""
    if auth_config is None:
        return None
    if isinstance(auth_config, (dict, list)):
        plaintext = json.dumps(auth_config)
    else:
        plaintext = str(auth_config)
    return encrypt_field(plaintext)


def _decrypt_auth_config_from_cipher(cipher: Optional[str]) -> Any:
    """Decrypt Fernet token and parse json if possible."""
    if not cipher:
        return None
    try:
        plaintext = decrypt_field(cipher)
        try:
            return json.loads(plaintext)
        except Exception:
            return plaintext
    except Exception as exc:
        logger.warning("Failed to decrypt external connection auth_config: %s", exc)
        return None


def create_connection(
    db: Session,
    data: ExternalConnectionCreate,
    workspace_id: Optional[str] = None,
    user_id: str = "default_user",
) -> ExternalConnection:
    """Create a new external connection with encrypted auth_config."""
    ws_id = str(workspace_id) if workspace_id else None

    # Check for duplicate name in same workspace
    existing = (
        db.query(ExternalConnection)
        .filter(
            ExternalConnection.name == data.name,
            ExternalConnection.workspace_id == ws_id if ws_id else ExternalConnection.workspace_id.is_(None),
        )
        .first()
    )
    if existing:
        raise ValueError(f"An external connection with name '{data.name}' already exists in this workspace.")

    conn = ExternalConnection(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        name=data.name,
        connector_type=data.connector_type or "custom",
        base_url=data.base_url,
        auth_config=_normalize_auth_config_to_cipher(data.auth_config),
        created_by=user_id,
        status=data.status or "active",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def list_connections(
    db: Session,
    workspace_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[ExternalConnection]:
    """List external connections for a workspace."""
    query = db.query(ExternalConnection)
    if workspace_id:
        ws_id = str(workspace_id)
        query = query.filter(
            (ExternalConnection.workspace_id == ws_id) | (ExternalConnection.workspace_id.is_(None))
        )
    if status:
        query = query.filter(ExternalConnection.status == status)

    return query.order_by(ExternalConnection.created_at.desc()).all()


def get_connection(
    db: Session,
    connection_id: str,
    workspace_id: Optional[str] = None,
) -> Optional[ExternalConnection]:
    """Fetch external connection by ID or name."""
    conn = db.query(ExternalConnection).filter(ExternalConnection.id == str(connection_id)).first()
    if not conn:
        conn = db.query(ExternalConnection).filter(ExternalConnection.name == str(connection_id)).first()
    return conn


def get_connection_by_name(
    db: Session,
    name: str,
    workspace_id: Optional[str] = None,
) -> Optional[ExternalConnection]:
    """Fetch external connection by user-facing name."""
    query = db.query(ExternalConnection).filter(ExternalConnection.name == name)
    if workspace_id:
        try:
            ws_uuid = uuid.UUID(str(workspace_id))
            query = query.filter(
                (ExternalConnection.workspace_id == ws_uuid) | (ExternalConnection.workspace_id.is_(None))
            )
        except Exception:
            pass
    return query.first()


def get_decrypted_auth_config(conn: ExternalConnection) -> Any:
    """Return decrypted auth_config object for internal execution dispatch only."""
    return _decrypt_auth_config_from_cipher(conn.auth_config)


def update_connection(
    db: Session,
    connection_id: str,
    data: ExternalConnectionUpdate,
    workspace_id: Optional[str] = None,
) -> ExternalConnection:
    """Update connection attributes and optionally re-encrypt auth_config."""
    conn = get_connection(db, connection_id, workspace_id)
    if not conn:
        raise ValueError(f"External connection '{connection_id}' not found.")

    if data.name is not None:
        conn.name = data.name
    if data.connector_type is not None:
        conn.connector_type = data.connector_type
    if data.base_url is not None:
        conn.base_url = data.base_url
    if data.auth_config is not None:
        conn.auth_config = _normalize_auth_config_to_cipher(data.auth_config)
    if data.status is not None:
        conn.status = data.status

    db.commit()
    db.refresh(conn)
    return conn


def disable_connection(
    db: Session,
    connection_id: str,
    workspace_id: Optional[str] = None,
) -> ExternalConnection:
    """Mark an external connection as disabled."""
    conn = get_connection(db, connection_id, workspace_id)
    if not conn:
        raise ValueError(f"External connection '{connection_id}' not found.")

    conn.status = "disabled"
    db.commit()
    db.refresh(conn)
    return conn


def delete_connection(
    db: Session,
    connection_id: str,
    workspace_id: Optional[str] = None,
) -> bool:
    """Delete an external connection."""
    conn = get_connection(db, connection_id, workspace_id)
    if not conn:
        return False

    db.delete(conn)
    db.commit()
    return True
