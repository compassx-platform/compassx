from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.job_config.repository import get_job_config
from app.ingestion.models import IngestionJobConfig


class UpdateJobConfig:
    def execute(
        self,
        db: Session,
        workspace_id: UUID,
        job_config_id: UUID,
        **fields,
    ) -> IngestionJobConfig:
        cfg = get_job_config(db, workspace_id, job_config_id)
        updatable = {
            "name", "http_method", "path_template", "query_template", "body_template",
            "pagination_type", "pagination_config", "cursor_field_path", "cursor_query_param",
            "param_source_type", "param_source_config", "target_bronze_bucket", "schedule_cron",
        }
        for key, value in fields.items():
            if key in updatable and value is not None:
                setattr(cfg, key, value)
        db.commit()
        db.refresh(cfg)
        return cfg


def update_job_config(
    db: Session,
    workspace_id: UUID,
    job_config_id: UUID,
    **fields,
) -> IngestionJobConfig:
    return UpdateJobConfig().execute(db, workspace_id, job_config_id, **fields)
