"""Shared connection lookup."""
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionConnection


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
