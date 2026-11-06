from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionRunItem


class GetRunItems:
    def execute(
        self,
        db: Session,
        run_id: UUID,
        status: Optional[str] = None,
    ) -> List[IngestionRunItem]:
        q = db.query(IngestionRunItem).filter(IngestionRunItem.run_id == run_id)
        if status:
            q = q.filter(IngestionRunItem.status == status)
        return q.order_by(IngestionRunItem.started_at).all()


def get_run_items(
    db: Session,
    run_id: UUID,
    status: Optional[str] = None,
) -> List[IngestionRunItem]:
    return GetRunItems().execute(db, run_id, status)
