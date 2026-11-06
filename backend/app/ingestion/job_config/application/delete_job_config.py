from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.job_config.repository import get_job_config


class DeleteJobConfig:
    def execute(self, db: Session, workspace_id: UUID, job_config_id: UUID) -> None:
        cfg = get_job_config(db, workspace_id, job_config_id)
        db.delete(cfg)
        db.commit()


def delete_job_config(db: Session, workspace_id: UUID, job_config_id: UUID) -> None:
    return DeleteJobConfig().execute(db, workspace_id, job_config_id)
