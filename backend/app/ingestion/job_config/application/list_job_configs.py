from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionJobConfig


class ListJobConfigs:
    def execute(
        self,
        db: Session,
        workspace_id: UUID,
        connection_id: Optional[UUID] = None,
    ) -> List[IngestionJobConfig]:
        q = db.query(IngestionJobConfig).filter(
            IngestionJobConfig.workspace_id == workspace_id
        )
        if connection_id:
            q = q.filter(IngestionJobConfig.connection_id == connection_id)
        return q.order_by(IngestionJobConfig.name).all()


def list_job_configs(
    db: Session,
    workspace_id: UUID,
    connection_id: Optional[UUID] = None,
) -> List[IngestionJobConfig]:
    return ListJobConfigs().execute(db, workspace_id, connection_id)
