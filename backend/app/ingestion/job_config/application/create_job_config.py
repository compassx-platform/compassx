from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionJobConfig


class CreateJobConfig:
    def execute(
        self,
        db: Session,
        workspace_id: UUID,
        connection_id: UUID,
        name: str,
        path_template: str,
        schedule_cron: str,
        created_by: UUID,
        http_method: str = "GET",
        query_template: Optional[dict] = None,
        body_template: Optional[dict] = None,
        pagination_type: str = "none",
        pagination_config: Optional[dict] = None,
        cursor_field_path: Optional[str] = None,
        cursor_query_param: Optional[str] = None,
        param_source_type: str = "static",
        param_source_config: Optional[dict] = None,
        target_bronze_bucket: str = "compassx-bronze",
        is_enabled: bool = True,
    ) -> IngestionJobConfig:
        cfg = IngestionJobConfig(
            id=uuid4(),
            workspace_id=workspace_id,
            connection_id=connection_id,
            name=name,
            http_method=http_method,
            path_template=path_template,
            query_template=query_template or {},
            body_template=body_template,
            pagination_type=pagination_type,
            pagination_config=pagination_config or {},
            cursor_field_path=cursor_field_path,
            cursor_query_param=cursor_query_param,
            param_source_type=param_source_type,
            param_source_config=param_source_config or {},
            target_bronze_bucket=target_bronze_bucket,
            schedule_cron=schedule_cron,
            is_enabled=is_enabled,
            created_by=created_by,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return cfg


def create_job_config(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
    name: str,
    path_template: str,
    schedule_cron: str,
    created_by: UUID,
    http_method: str = "GET",
    query_template: Optional[dict] = None,
    body_template: Optional[dict] = None,
    pagination_type: str = "none",
    pagination_config: Optional[dict] = None,
    cursor_field_path: Optional[str] = None,
    cursor_query_param: Optional[str] = None,
    param_source_type: str = "static",
    param_source_config: Optional[dict] = None,
    target_bronze_bucket: str = "compassx-bronze",
    is_enabled: bool = True,
) -> IngestionJobConfig:
    return CreateJobConfig().execute(
        db, workspace_id, connection_id, name, path_template, schedule_cron, created_by,
        http_method, query_template, body_template, pagination_type, pagination_config,
        cursor_field_path, cursor_query_param, param_source_type, param_source_config,
        target_bronze_bucket, is_enabled,
    )
