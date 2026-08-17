"""
Job Config service layer — CRUD for ingestion_job_config.
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionJobConfig

logger = logging.getLogger(__name__)


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
    cfg = IngestionJobConfig(
        id=uuid.uuid4(),
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


def list_job_configs(
    db: Session,
    workspace_id: UUID,
    connection_id: Optional[UUID] = None,
) -> List[IngestionJobConfig]:
    q = db.query(IngestionJobConfig).filter(
        IngestionJobConfig.workspace_id == workspace_id
    )
    if connection_id:
        q = q.filter(IngestionJobConfig.connection_id == connection_id)
    return q.order_by(IngestionJobConfig.name).all()


def update_job_config(
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


def enable_job_config(
    db: Session, workspace_id: UUID, job_config_id: UUID
) -> None:
    cfg = get_job_config(db, workspace_id, job_config_id)
    cfg.is_enabled = True
    db.commit()


def disable_job_config(
    db: Session, workspace_id: UUID, job_config_id: UUID
) -> None:
    cfg = get_job_config(db, workspace_id, job_config_id)
    cfg.is_enabled = False
    db.commit()


def delete_job_config(
    db: Session, workspace_id: UUID, job_config_id: UUID
) -> None:
    cfg = get_job_config(db, workspace_id, job_config_id)
    db.delete(cfg)
    db.commit()
