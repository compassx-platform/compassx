from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ingestion.models import IngestionWatermark


class AdvanceWatermark:
    def execute(
        self,
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


def advance_watermark(
    db: Session,
    job_config_id: UUID,
    param_value: str,
    cursor_value: Optional[str],
    run_id: UUID,
) -> None:
    return AdvanceWatermark().execute(db, job_config_id, param_value, cursor_value, run_id)
