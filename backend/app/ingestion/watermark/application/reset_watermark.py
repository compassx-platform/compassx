from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.composition import watermark_logger
from app.ingestion.models import IngestionWatermark

logger = watermark_logger()


class ResetWatermark:
    def execute(
        self,
        db: Session,
        job_config_id: UUID,
        param_value: Optional[str] = None,
    ) -> None:
        """
        Reset watermark(s) for a job config.
        param_value=None → reset ALL params for this job (full re-backfill).
        """
        q = db.query(IngestionWatermark).filter(
            IngestionWatermark.job_config_id == job_config_id
        )
        if param_value is not None:
            q = q.filter(IngestionWatermark.param_value == param_value)
        q.delete(synchronize_session=False)
        db.commit()
        logger.info(
            "Watermark reset: job_config_id=%s param_value=%s",
            job_config_id,
            param_value or "*",
        )


def reset_watermark(
    db: Session,
    job_config_id: UUID,
    param_value: Optional[str] = None,
) -> None:
    return ResetWatermark().execute(db, job_config_id, param_value)
