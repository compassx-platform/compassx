"""
Ingestion module REST API routes.

Prefix: /api/v1/workspaces/{workspace_id}/ingestion
Auth:   get_current_user (workspace-scoped; object-level RBAC is a fast-follow)
DB:     get_system_db
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.dependencies import get_current_user

from app.ingestion import connections as conn_svc
from app.ingestion import job_configs as jc_svc
from app.ingestion import observability as obs_svc
from app.ingestion import watermarks as wm_svc
from app.ingestion.schemas import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionRotateSecret,
    ConnectionUpdate,
    JobConfigCreate,
    JobConfigOut,
    JobConfigUpdate,
    RunItemOut,
    RunSummaryOut,
    TriggerOut,
    WatermarkResetIn,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}/ingestion",
    tags=["ingestion"],
    dependencies=[Depends(get_current_user)],
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _conn_out(c) -> ConnectionOut:
    return ConnectionOut(
        id=c.id,
        workspace_id=c.workspace_id,
        name=c.name,
        description=c.description,
        base_url=c.base_url,
        auth_type=c.auth_type,
        auth_config=c.auth_config or {},
        has_secret=c.secret_ref is not None,
        default_headers=c.default_headers or {},
        rate_limit_rps=float(c.rate_limit_rps),
        max_concurrency=c.max_concurrency,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _jc_out(cfg) -> JobConfigOut:
    return JobConfigOut(
        id=cfg.id,
        workspace_id=cfg.workspace_id,
        connection_id=cfg.connection_id,
        name=cfg.name,
        http_method=cfg.http_method,
        path_template=cfg.path_template,
        query_template=cfg.query_template or {},
        body_template=cfg.body_template,
        pagination_type=cfg.pagination_type,
        pagination_config=cfg.pagination_config or {},
        cursor_field_path=cfg.cursor_field_path,
        cursor_query_param=cfg.cursor_query_param,
        param_source_type=cfg.param_source_type,
        param_source_config=cfg.param_source_config or {},
        target_bronze_bucket=cfg.target_bronze_bucket,
        schedule_cron=cfg.schedule_cron,
        is_enabled=cfg.is_enabled,
        created_by=cfg.created_by,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


def _run_out(r) -> RunSummaryOut:
    return RunSummaryOut(
        id=r.id,
        job_config_id=r.job_config_id,
        airflow_dag_run_id=r.airflow_dag_run_id,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        total_params=r.total_params or 0,
        succeeded_params=r.succeeded_params or 0,
        failed_params=r.failed_params or 0,
        total_rows_landed=r.total_rows_landed or 0,
        total_bytes_landed=r.total_bytes_landed or 0,
        error_summary=r.error_summary,
    )


def _item_out(i) -> RunItemOut:
    return RunItemOut(
        id=i.id,
        run_id=i.run_id,
        param_value=i.param_value,
        status=i.status,
        pages_fetched=i.pages_fetched or 0,
        rows_landed=i.rows_landed or 0,
        bytes_landed=i.bytes_landed or 0,
        bronze_path=i.bronze_path,
        error_message=i.error_message,
        started_at=i.started_at,
        finished_at=i.finished_at,
    )


def _current_user_id(current_user) -> UUID:
    uid = getattr(current_user, "user_id", None) or getattr(current_user, "id", None)
    if uid:
        return UUID(str(uid))
    return uuid.uuid4()


# ── Connections ───────────────────────────────────────────────────────────────

@router.post("/connections", response_model=ConnectionOut, status_code=201)
def create_connection(
    workspace_id: UUID,
    body: ConnectionCreate,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        c = conn_svc.create_connection(
            db=db,
            workspace_id=workspace_id,
            name=body.name,
            description=body.description,
            base_url=body.base_url,
            auth_type=body.auth_type,
            auth_config=body.auth_config,
            secret_value=body.secret_value,
            default_headers=body.default_headers,
            rate_limit_rps=body.rate_limit_rps,
            max_concurrency=body.max_concurrency,
            created_by=_current_user_id(current_user),
        )
        return _conn_out(c)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections", response_model=List[ConnectionOut])
def list_connections(
    workspace_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    return [_conn_out(c) for c in conn_svc.list_connections(db, workspace_id)]


@router.get("/connections/{connection_id}", response_model=ConnectionOut)
def get_connection(
    workspace_id: UUID,
    connection_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        return _conn_out(conn_svc.get_connection(db, workspace_id, connection_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/connections/{connection_id}", response_model=ConnectionOut)
def update_connection(
    workspace_id: UUID,
    connection_id: UUID,
    body: ConnectionUpdate,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        c = conn_svc.update_connection(
            db, workspace_id, connection_id,
            **{k: v for k, v in body.model_dump(exclude_unset=True).items()},
        )
        return _conn_out(c)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/connections/{connection_id}/rotate-secret", status_code=204)
def rotate_secret(
    workspace_id: UUID,
    connection_id: UUID,
    body: ConnectionRotateSecret,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        conn_svc.rotate_connection_secret(db, workspace_id, connection_id, body.new_secret_value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/connections/{connection_id}", status_code=204)
def delete_connection(
    workspace_id: UUID,
    connection_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        conn_svc.delete_connection(db, workspace_id, connection_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Job Configs ───────────────────────────────────────────────────────────────

@router.post("/job-configs", response_model=JobConfigOut, status_code=201)
def create_job_config(
    workspace_id: UUID,
    body: JobConfigCreate,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        cfg = jc_svc.create_job_config(
            db=db,
            workspace_id=workspace_id,
            connection_id=body.connection_id,
            name=body.name,
            http_method=body.http_method,
            path_template=body.path_template,
            query_template=body.query_template,
            body_template=body.body_template,
            pagination_type=body.pagination_type,
            pagination_config=body.pagination_config,
            cursor_field_path=body.cursor_field_path,
            cursor_query_param=body.cursor_query_param,
            param_source_type=body.param_source_type,
            param_source_config=body.param_source_config,
            target_bronze_bucket=body.target_bronze_bucket,
            schedule_cron=body.schedule_cron,
            is_enabled=body.is_enabled,
            created_by=_current_user_id(current_user),
        )
        return _jc_out(cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/job-configs", response_model=List[JobConfigOut])
def list_job_configs(
    workspace_id: UUID,
    connection_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    return [_jc_out(cfg) for cfg in jc_svc.list_job_configs(db, workspace_id, connection_id)]


@router.get("/job-configs/{job_config_id}", response_model=JobConfigOut)
def get_job_config(
    workspace_id: UUID,
    job_config_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        return _jc_out(jc_svc.get_job_config(db, workspace_id, job_config_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/job-configs/{job_config_id}", response_model=JobConfigOut)
def update_job_config(
    workspace_id: UUID,
    job_config_id: UUID,
    body: JobConfigUpdate,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        cfg = jc_svc.update_job_config(
            db, workspace_id, job_config_id,
            **{k: v for k, v in body.model_dump(exclude_unset=True).items()},
        )
        return _jc_out(cfg)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/job-configs/{job_config_id}/enable", status_code=204)
def enable_job_config(
    workspace_id: UUID,
    job_config_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        jc_svc.enable_job_config(db, workspace_id, job_config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/job-configs/{job_config_id}/disable", status_code=204)
def disable_job_config(
    workspace_id: UUID,
    job_config_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        jc_svc.disable_job_config(db, workspace_id, job_config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/job-configs/{job_config_id}/trigger", response_model=TriggerOut)
def trigger_run(
    workspace_id: UUID,
    job_config_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    """Enqueue a manual run in the background. Returns run_id immediately."""
    try:
        cfg = jc_svc.get_job_config(db, workspace_id, job_config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not cfg.is_enabled:
        raise HTTPException(status_code=400, detail="Job config is disabled. Enable it before triggering.")

    # Create the run record synchronously so we can return run_id immediately
    from app.ingestion.models import IngestionRun
    run = IngestionRun(
        id=uuid.uuid4(),
        job_config_id=job_config_id,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id

    def _bg_execute():
        from app.database import SystemSessionLocal
        bg_db = SystemSessionLocal()
        try:
            from app.ingestion.execution import execute_run
            execute_run(bg_db, job_config_id, workspace_id)
        except Exception as exc:
            logger.error("Background execute_run failed for run %s: %s", run_id, exc, exc_info=True)
        finally:
            bg_db.close()

    background_tasks.add_task(_bg_execute)

    return TriggerOut(run_id=run_id, status="running")


@router.delete("/job-configs/{job_config_id}", status_code=204)
def delete_job_config(
    workspace_id: UUID,
    job_config_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        jc_svc.delete_job_config(db, workspace_id, job_config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Runs ──────────────────────────────────────────────────────────────────────

@router.get("/job-configs/{job_config_id}/runs", response_model=List[RunSummaryOut])
def list_runs(
    workspace_id: UUID,
    job_config_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    return [_run_out(r) for r in obs_svc.list_runs(db, job_config_id, limit, status)]


@router.get("/runs/{run_id}", response_model=RunSummaryOut)
def get_run(
    workspace_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    try:
        return _run_out(obs_svc.get_run(db, run_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/runs/{run_id}/items", response_model=List[RunItemOut])
def get_run_items(
    workspace_id: UUID,
    run_id: UUID,
    status: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    return [_item_out(i) for i in obs_svc.get_run_items(db, run_id, status)]


# ── Watermarks ────────────────────────────────────────────────────────────────

@router.post("/job-configs/{job_config_id}/watermarks/reset", status_code=204)
def reset_watermark(
    workspace_id: UUID,
    job_config_id: UUID,
    body: WatermarkResetIn,
    db: Session = Depends(get_system_db),
    current_user=Depends(get_current_user),
):
    wm_svc.reset_watermark(db, job_config_id, body.param_value)
