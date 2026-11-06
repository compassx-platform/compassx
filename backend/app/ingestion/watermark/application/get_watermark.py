from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionWatermark
from app.ingestion.watermark.constants import NONE_SENTINEL


class GetWatermark:
    def execute(
        self,
        db: Session,
        job_config_id: UUID,
        param_value: str = NONE_SENTINEL,
    ) -> Optional[IngestionWatermark]:
        return (
            db.query(IngestionWatermark)
            .filter(
                IngestionWatermark.job_config_id == job_config_id,
                IngestionWatermark.param_value == param_value,
            )
            .first()
        )


def get_watermark(
    db: Session,
    job_config_id: UUID,
    param_value: str = NONE_SENTINEL,
) -> Optional[IngestionWatermark]:
    return GetWatermark().execute(db, job_config_id, param_value)
