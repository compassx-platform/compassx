from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.connection.repository import get_connection


class DeleteConnection:
    def execute(
        self,
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


def delete_connection(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
) -> None:
    return DeleteConnection().execute(db, workspace_id, connection_id)
