from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.connection.repository import get_connection
from app.ingestion.models import IngestionConnection


class UpdateConnection:
    def execute(
        self,
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


def update_connection(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
    **fields,
) -> IngestionConnection:
    return UpdateConnection().execute(db, workspace_id, connection_id, **fields)
