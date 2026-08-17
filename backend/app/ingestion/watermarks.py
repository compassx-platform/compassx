"""
Watermark service — tracks incremental cursor state per (job_config, param_value).

Per spec D6 and D8:
  - Watermark lives in ingestion_watermark, keyed by (job_config_id, param_value).
  - '__none__' is the sentinel param_value for non-parameterised jobs.
  - Watermark only advances on full per-param success (at-least-once semantics).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingestion.models import IngestionWatermark

logger = logging.getLogger(__name__)

NONE_SENTINEL = "__none__"


def get_watermark(
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


def advance_watermark(
    db: Session,
    job_config_id: UUID,
    param_value: str,
    cursor_value: Optional[str],
    run_id: UUID,
) -> None:
    """Upsert the watermark row. Only called on per-param success (D8)."""
    now = datetime.now(timezone.utc)

    stmt = (
        pg_insert(IngestionWatermark)
        .values(
            job_config_id=job_config_id,
            param_value=param_value,
            cursor_value=cursor_value,
            last_success_at=now,
            last_run_id=run_id,
        )
        .on_conflict_do_update(
            index_elements=["job_config_id", "param_value"],
            set_={
                "cursor_value": cursor_value,
                "last_success_at": now,
                "last_run_id": run_id,
            },
        )
    )
    db.execute(stmt)
    db.commit()


def reset_watermark(
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
