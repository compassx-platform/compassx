"""
Jobs module REST API routes.

Prefix: /api/v1/jobs

Handlers stay here. Each one forwards to one application type.
Helper names stay importable from ``app.jobs.routes``.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.dependencies import get_current_user
from app.governance.dependencies import Guard, get_guard
from app.jobs.definition.application.archive_job import archive_job as archive_job_action
from app.jobs.definition.application.create_job import _ensure_schema
from app.jobs.definition.application.create_job import create_job as create_job_action
from app.jobs.definition.application.delete_job import delete_job as delete_job_action
from app.jobs.definition.application.get_job import get_job as get_job_action
from app.jobs.definition.application.get_publish_status import get_publish_status as get_publish_status_action
from app.jobs.definition.application.get_version import get_version as get_version_action
from app.jobs.definition.application.list_jobs import list_jobs as list_jobs_action
from app.jobs.definition.application.pause_job import pause_job as pause_job_action
from app.jobs.definition.application.publish_job import publish_job as publish_job_action
from app.jobs.definition.application.resume_job import resume_job as resume_job_action
from app.jobs.definition.application.save_draft import save_draft as save_draft_action
from app.jobs.definition.application.update_job import update_job as update_job_action
from app.jobs.dependencies import get_scheduler_gateway
from app.jobs.interfaces import SchedulerGateway
from app.jobs.run.application.airflow_task_state import airflow_task_state as airflow_task_state_action
from app.jobs.run.application.cancel_run import cancel_run as cancel_run_action
from app.jobs.run.application.get_run import get_run as get_run_action
from app.jobs.run.application.list_runs import list_runs as list_runs_action
from app.jobs.run.application.rerun import rerun as rerun_action
from app.jobs.run.application.retry_task import retry_task as retry_task_action
from app.jobs.run.application.trigger_run import trigger_run as trigger_run_action
from app.jobs.schemas import (
    DraftUpdate,
    JobCreate,
    JobOut,
    JobRunOut,
    JobUpdate,
    JobVersionOut,
    RunTriggerIn,
)
from app.jobs.shared.support import (
    _authorized_job,
    _authorized_run,
    _create_run_records,
    _duration,
    _get_draft_version,
    _get_published_version,
    _job_id,
    _job_out,
    _job_run_out,
    _last_run,
    _task_run_out,
    _trigger_scheduler,
    _utcnow,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[JobOut])
def list_jobs(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return list_jobs_action(search, status, db, guard)


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return create_job_action(body, db, guard)


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return get_job_action(job_id, db, guard)


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: str,
    body: JobUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return update_job_action(job_id, body, db, guard)


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return delete_job_action(job_id, db, guard)


@router.put("/{job_id}/draft", response_model=JobVersionOut)
def save_draft(
    job_id: str,
    body: DraftUpdate,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return save_draft_action(job_id, body, db, guard)


@router.post("/{job_id}/publish", response_model=JobOut)
def publish_job(
    job_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return publish_job_action(job_id, db, guard)


@router.get("/{job_id}/status")
def get_publish_status(
    job_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return get_publish_status_action(job_id, gateway, db, guard)


@router.get("/{job_id}/version", response_model=JobVersionOut)
def get_version(
    job_id: str,
    which: str = Query("published"),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return get_version_action(job_id, which, db, guard)


@router.post("/{job_id}/pause", response_model=JobOut)
def pause_job(
    job_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return pause_job_action(job_id, gateway, db, guard)


@router.post("/{job_id}/resume", response_model=JobOut)
def resume_job(
    job_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return resume_job_action(job_id, gateway, db, guard)


@router.post("/{job_id}/archive", response_model=JobOut)
def archive_job(
    job_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return archive_job_action(job_id, db, guard)


@router.post("/{job_id}/run", response_model=JobRunOut, status_code=201)
def trigger_run(
    job_id: str,
    body: RunTriggerIn = RunTriggerIn(),
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return trigger_run_action(job_id, body, gateway, db, guard)


@router.get("/{job_id}/runs", response_model=List[JobRunOut])
def list_runs(
    job_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return list_runs_action(job_id, limit, offset, db, guard)


run_router = APIRouter(
    prefix="/api/v1/job-runs",
    tags=["job-runs"],
    dependencies=[Depends(get_current_user)],
)


@run_router.get("/{run_id}", response_model=JobRunOut)
def get_run(
    run_id: str,
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return get_run_action(run_id, db, guard)


@run_router.post("/{run_id}/cancel", response_model=JobRunOut)
def cancel_run(
    run_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return cancel_run_action(run_id, gateway, db, guard)


@run_router.post("/{run_id}/rerun", response_model=JobRunOut, status_code=201)
def rerun(
    run_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return rerun_action(run_id, gateway, db, guard)


@run_router.post("/{run_id}/tasks/{task_key}/retry", response_model=JobRunOut)
def retry_task(
    run_id: str,
    task_key: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
    guard: Guard = Depends(get_guard),
):
    return retry_task_action(run_id, task_key, gateway, db, guard)


webhook_router = APIRouter(prefix="/api/v1/webhooks/airflow", tags=["airflow-webhook"])


class TaskStateIn:
    dag_id: str
    dag_run_id: str
    task_id: str
    try_number: int
    state: str
    timestamp: str


@webhook_router.post("/task-state", status_code=200)
async def airflow_task_state(
    request: Request,
    x_compassx_signature: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    return await airflow_task_state_action(request, x_compassx_signature, db)
