from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.job_config.repository import get_job_config as find_job_config
from app.ingestion.models import IngestionJobConfig


class GetJobConfig:
    def execute(self, db: Session, workspace_id: UUID, job_config_id: UUID) -> IngestionJobConfig:
        return find_job_config(db, workspace_id, job_config_id)


def get_job_config(db: Session, workspace_id: UUID, job_config_id: UUID) -> IngestionJobConfig:
    return GetJobConfig().execute(db, workspace_id, job_config_id)
