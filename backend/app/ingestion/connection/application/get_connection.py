from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.connection.repository import get_connection as find_connection
from app.ingestion.models import IngestionConnection


class GetConnection:
    def execute(self, db: Session, workspace_id: UUID, connection_id: UUID) -> IngestionConnection:
        return find_connection(db, workspace_id, connection_id)


def get_connection(db: Session, workspace_id: UUID, connection_id: UUID) -> IngestionConnection:
    return GetConnection().execute(db, workspace_id, connection_id)
