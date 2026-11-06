from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionConnection


class ListConnections:
    def execute(self, db: Session, workspace_id: UUID) -> List[IngestionConnection]:
        return (
            db.query(IngestionConnection)
            .filter(IngestionConnection.workspace_id == workspace_id)
            .order_by(IngestionConnection.name)
            .all()
        )


def list_connections(db: Session, workspace_id: UUID) -> List[IngestionConnection]:
    return ListConnections().execute(db, workspace_id)
