from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionRun


class ListRuns:
    def execute(
        self,
        db: Session,
        job_config_id: UUID,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> List[IngestionRun]:
        q = db.query(IngestionRun).filter(IngestionRun.job_config_id == job_config_id)
        if status:
            q = q.filter(IngestionRun.status == status)
        return q.order_by(IngestionRun.started_at.desc()).limit(limit).all()


def list_runs(
    db: Session,
    job_config_id: UUID,
    limit: int = 50,
    status: Optional[str] = None,
) -> List[IngestionRun]:
    return ListRuns().execute(db, job_config_id, limit, status)
