from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionRun


class GetRun:
    def execute(self, db: Session, run_id: UUID) -> IngestionRun:
        run = db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        return run


def get_run(db: Session, run_id: UUID) -> IngestionRun:
    return GetRun().execute(db, run_id)
