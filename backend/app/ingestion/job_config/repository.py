"""Shared job-config lookup."""
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionJobConfig


def get_job_config(
    db: Session, workspace_id: UUID, job_config_id: UUID
) -> IngestionJobConfig:
    cfg = (
        db.query(IngestionJobConfig)
        .filter(
            IngestionJobConfig.id == job_config_id,
            IngestionJobConfig.workspace_id == workspace_id,
        )
        .first()
    )
    if not cfg:
        raise ValueError(f"Job config {job_config_id} not found")
    return cfg
