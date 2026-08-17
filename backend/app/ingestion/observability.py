"""
Observability service — run and run-item queries.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionRun, IngestionRunItem

logger = logging.getLogger(__name__)


def get_run(db: Session, run_id: UUID) -> IngestionRun:
    run = db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")
    return run


def list_runs(
    db: Session,
    job_config_id: UUID,
    limit: int = 50,
    status: Optional[str] = None,
) -> List[IngestionRun]:
    q = db.query(IngestionRun).filter(IngestionRun.job_config_id == job_config_id)
    if status:
        q = q.filter(IngestionRun.status == status)
    return q.order_by(IngestionRun.started_at.desc()).limit(limit).all()


def get_run_items(
    db: Session,
    run_id: UUID,
    status: Optional[str] = None,
) -> List[IngestionRunItem]:
    q = db.query(IngestionRunItem).filter(IngestionRunItem.run_id == run_id)
    if status:
        q = q.filter(IngestionRunItem.status == status)
    return q.order_by(IngestionRunItem.started_at).all()
