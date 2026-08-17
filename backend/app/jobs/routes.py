"""
Jobs module REST API routes.

Prefix: /api/v1/jobs
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.dependencies import get_current_user
from app.jobs.dependencies import get_scheduler_gateway
from app.jobs.assets import missing_notebook_targets
from app.jobs.execution_service import task_executors
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import Job, JobStatus, JobVersion, AirflowJobSpec
from app.jobs.models.run_trace import (
    JobRun,
    TaskRun,
    RunState,
    TriggerType,
    TaskRunState,
)
from app.jobs.security import verify_airflow_signature
from app.jobs.tokens import mint_execution_token
from app.jobs.validation import validate_job_spec
from app.jobs.schemas import (
    DraftUpdate,
    JobCreate,
    JobOut,
    JobRunOut,
    JobUpdate,
    JobVersionOut,
    RunTriggerIn,
    TaskRunOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["jobs"],
    dependencies=[Depends(get_current_user)],
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _duration(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    if start and end:
        return round((end - start).total_seconds(), 1)
    return None


def _task_run_out(tr: TaskRun) -> TaskRunOut:
    return TaskRunOut(
        task_run_id=tr.task_run_id,
        job_run_id=tr.job_run_id,
        task_key=tr.task_key,
        try_number=tr.try_number,
        state=tr.state.value if tr.state else "queued",
        execution_ref=tr.execution_ref,
        started_at=tr.started_at,
        ended_at=tr.ended_at,
        duration_seconds=_duration(tr.started_at, tr.ended_at),
    )


def _job_run_out(run: JobRun, include_tasks: bool = False) -> JobRunOut:
    return JobRunOut(
        job_run_id=run.job_run_id,
        job_id=run.job_id,
        job_version=run.job_version,
        dag_run_id=run.dag_run_id,
        trigger_type=run.trigger_type.value if run.trigger_type else "manual",
        triggered_by=run.triggered_by,
        parent_job_run_id=run.parent_job_run_id,
        state=run.state.value if run.state else "queued",
        started_at=run.started_at,
        ended_at=run.ended_at,
        last_synced_at=run.last_synced_at,
        duration_seconds=_duration(run.started_at, run.ended_at),
        task_runs=[_task_run_out(tr) for tr in run.task_runs] if include_tasks else [],
    )


def _get_published_version(job: Job, db: Session) -> Optional[JobVersion]:
    if job.current_version is None:
        return None
    return (
        db.query(JobVersion)
        .filter(
            JobVersion.job_id == job.job_id,
            JobVersion.version_number == job.current_version,
        )
        .first()
    )


def _get_draft_version(job: Job, db: Session) -> Optional[JobVersion]:
    if job.draft_version is None:
        return None
    return (
        db.query(JobVersion)
        .filter(
            JobVersion.job_id == job.job_id,
            JobVersion.version_number == job.draft_version,
        )
        .first()
    )


def _last_run(job: Job, db: Session) -> Optional[JobRun]:
    return (
        db.query(JobRun)
        .filter(JobRun.job_id == job.job_id)
        .order_by(JobRun.started_at.desc().nullslast(), JobRun.last_synced_at.desc().nullslast())
        .first()
    )


def _job_out(job: Job, db: Session) -> JobOut:
    pub = _get_published_version(job, db)
    draft = _get_draft_version(job, db)
    ver = draft or pub
    last = _last_run(job, db)
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()

    task_defs = ver.task_definitions if ver else []

    recent_runs = (
        db.query(JobRun)
        .filter(JobRun.job_id == job.job_id)
        .order_by(JobRun.started_at.desc().nullslast(), JobRun.last_synced_at.desc().nullslast())
        .limit(5)
        .all()
    )
    recent_run_outs = [_job_run_out(r, include_tasks=False) for r in reversed(recent_runs)]

    return JobOut(
        job_id=job.job_id,
        workspace_id=job.workspace_id,
        name=job.name,
        description=job.description,
        owner_user_id=job.owner_user_id,
        status=job.status.value if job.status else "active",
        current_version=job.current_version,
        draft_version=job.draft_version,
        has_unpublished_changes=job.draft_version is not None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        schedule_cron=ver.schedule_cron if ver else None,
        timezone=ver.timezone if ver else "UTC",
        max_active_runs=ver.max_active_runs if ver else 1,
        retry_policy=ver.retry_policy if ver else {},
        task_definitions=task_defs if task_defs else [],
        last_run_state=last.state.value if last else None,
        last_run_started_at=last.started_at if last else None,
        last_run_id=last.job_run_id if last else None,
        task_count=len(task_defs) if task_defs else 0,
        recent_runs=recent_run_outs,
        publish_state=spec.publish_state if spec else None,
        airflow_confirmed_at=spec.airflow_confirmed_at if spec else None,
    )


def _create_run_records(
    db: Session,
    job: Job,
    version: JobVersion,
    *,
    trigger_type: TriggerType,
    triggered_by: str | None,
    parent_job_run_id=None,
) -> tuple[JobRun, dict[str, str], dict[str, str]]:
    prefix = "rerun" if trigger_type == TriggerType.rerun else "manual"
    dag_run_id = f"compassx_{prefix}_{uuid.uuid4().hex[:16]}"
    run = JobRun(
        job_id=job.job_id,
        job_version=version.version_number,
        dag_run_id=dag_run_id,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        parent_job_run_id=parent_job_run_id,
        state=RunState.queued,
        last_synced_at=_utcnow(),
    )
    db.add(run)
    db.flush()
    token_refs: dict[str, str] = {}
    task_run_ids: dict[str, str] = {}
    for definition in version.task_definitions or []:
        task_key = definition["task_key"]
        task_run = TaskRun(
            job_run_id=run.job_run_id,
            task_key=task_key,
            dag_run_id=dag_run_id,
            airflow_task_id=task_key,
            try_number=1,
            state=TaskRunState.queued,
            last_synced_at=_utcnow(),
        )
        db.add(task_run)
        db.flush()
        token = mint_execution_token(
            db,
            run,
            task_key,
            user_id=job.owner_user_id,
            workspace_id=job.workspace_id,
        )
        token_refs[task_key] = str(token.token_id)
        task_run_ids[task_key] = str(task_run.task_run_id)
    return run, token_refs, task_run_ids


def _trigger_scheduler(
    gateway: SchedulerGateway,
    spec: AirflowJobSpec,
    run: JobRun,
    token_refs: dict[str, str],
    task_run_ids: dict[str, str],
) -> None:
    if not gateway.dag_exists(spec.dag_id):
        raise HTTPException(
            status_code=409,
            detail="Job is still publishing. Wait for the scheduler to register it.",
        )
    gateway.trigger_run(
        spec.dag_id,
        run.dag_run_id,
        {
            "job_run_id": str(run.job_run_id),
            "execution_token_refs": token_refs,
            "task_run_ids": task_run_ids,
        },
    )


def _ensure_schema(db: Session) -> None:
    """Create the jobs schema if it doesn't exist (idempotent, called at request time)."""
    try:
        db.execute(text("CREATE SCHEMA IF NOT EXISTS jobs"))
        db.commit()
    except Exception:
        db.rollback()


# ── Jobs CRUD ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[JobOut])
def list_jobs(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_system_db),
):
    """List all jobs, optionally filtered by status/search/workspace."""
    q = db.query(Job)
    if status:
        try:
            q = q.filter(Job.status == JobStatus(status))
        except ValueError:
            pass
    if search:
        q = q.filter(Job.name.ilike(f"%{search}%"))
    if workspace_id:
        try:
            q = q.filter(Job.workspace_id == uuid.UUID(workspace_id))
        except ValueError:
            pass
    jobs = q.order_by(Job.updated_at.desc()).all()
    return [_job_out(j, db) for j in jobs]


@router.post("", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_system_db),
):
    """Create a new job with an initial empty draft version."""
    _ensure_schema(db)
    job = Job(
        name=body.name,
        description=body.description,
        workspace_id=(
            body.workspace_id
            or getattr(getattr(request.state, "workspace", None), "workspace_id", None)
        ),
        owner_user_id=current_user.get("id"),
        status=JobStatus.active,
        current_version=None,
        draft_version=None,
    )
    db.add(job)
    db.flush()

    # Create version 1 as draft
    ver = JobVersion(
        job_id=job.job_id,
        version_number=1,
        is_published=False,
        task_definitions=[],
        retry_policy={},
        created_by=current_user.get("id"),
    )
    db.add(ver)
    db.flush()
    job.draft_version = 1
    db.commit()
    db.refresh(job)
    return _job_out(job, db)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_system_db)):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job, db)


@router.put("/{job_id}", response_model=JobOut)
def update_job(job_id: str, body: JobUpdate, db: Session = Depends(get_system_db)):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.name is not None:
        job.name = body.name
    if body.description is not None:
        job.description = body.description
    job.updated_at = _utcnow()
    db.commit()
    db.refresh(job)
    return _job_out(job, db)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, db: Session = Depends(get_system_db)):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()


# ── Draft management ──────────────────────────────────────────────────────────

@router.put("/{job_id}/draft", response_model=JobVersionOut)
def save_draft(
    job_id: str,
    body: DraftUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_system_db),
):
    """
    Autosave the draft version for a job.
    Creates a new draft version if none exists, or updates the existing one.
    """
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Versions are immutable snapshots. Every explicit save appends a row and
    # moves the draft pointer; prior drafts remain available for audit.
    latest_version = (
        db.query(func.max(JobVersion.version_number))
        .filter(JobVersion.job_id == job.job_id)
        .scalar()
        or 0
    )
    draft = JobVersion(
        job_id=job.job_id,
        version_number=latest_version + 1,
        schedule_cron=body.schedule_cron,
        timezone=body.timezone,
        max_active_runs=body.max_active_runs,
        retry_policy=body.retry_policy.model_dump(),
        task_definitions=[t.model_dump() for t in body.task_definitions],
        is_published=False,
        created_by=current_user.get("id"),
    )
    db.add(draft)
    db.flush()
    job.draft_version = draft.version_number
    job.updated_at = _utcnow()
    db.commit()
    db.refresh(draft)
    return JobVersionOut.model_validate(draft)


@router.post("/{job_id}/publish", response_model=JobOut)
def publish_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_system_db),
):
    """
    Publish the current draft: mark it published, update current_version pointer,
    upsert airflow_job_specs for DAG factory consumption.
    """
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.draft_version is None:
        raise HTTPException(status_code=400, detail="No draft version to publish")

    draft = _get_draft_version(job, db)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft version not found")
    validate_job_spec(draft.schedule_cron, draft.task_definitions or [])
    for task in draft.task_definitions or []:
        if task.get("task_type") not in task_executors.registered_types():
            raise HTTPException(
                status_code=422,
                detail=f"No local-dev execution adapter is available for task type: {task.get('task_type')}",
            )
    try:
        missing_targets = missing_notebook_targets(
            draft.task_definitions or [],
            workspace_id=str(job.workspace_id) if job.workspace_id else None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Notebook storage is unavailable; publishing cannot be validated.",
        ) from exc
    if missing_targets:
        raise HTTPException(
            status_code=422,
            detail=f"Notebook does not exist: {missing_targets[0]}",
        )

    # Mark published
    draft.is_published = True
    draft.published_at = _utcnow()
    draft.published_by = current_user.get("id")

    # Promote
    job.current_version = draft.version_number
    job.draft_version = None
    job.status = JobStatus.active
    job.updated_at = _utcnow()

    # Upsert airflow_job_specs
    dag_id = f"compassx_job_{job.job_id}"
    spec_payload = {
        "dag_id": dag_id,
        "schedule_cron": draft.schedule_cron,
        "timezone": draft.timezone,
        "max_active_runs": draft.max_active_runs,
        "retry_policy": draft.retry_policy,
        "resolved_tasks": draft.task_definitions,
        "workspace_id": str(job.workspace_id) if job.workspace_id else None,
    }
    checksum = hashlib.md5(json.dumps(spec_payload, sort_keys=True).encode()).hexdigest()

    existing_spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if existing_spec:
        existing_spec.dag_id = dag_id
        existing_spec.job_version = draft.version_number
        existing_spec.workspace_id = job.workspace_id
        existing_spec.schedule_cron = draft.schedule_cron
        existing_spec.timezone = draft.timezone
        existing_spec.max_active_runs = draft.max_active_runs
        existing_spec.retry_policy = draft.retry_policy or {}
        existing_spec.resolved_tasks = draft.task_definitions or []
        existing_spec.is_active = True
        existing_spec.spec_checksum = checksum
        existing_spec.publish_state = "publishing"
        existing_spec.airflow_confirmed_at = None
        existing_spec.updated_at = _utcnow()
    else:
        spec = AirflowJobSpec(
            job_id=job.job_id,
            dag_id=dag_id,
            job_version=draft.version_number,
            workspace_id=job.workspace_id,
            schedule_cron=draft.schedule_cron,
            timezone=draft.timezone,
            max_active_runs=draft.max_active_runs,
            retry_policy=draft.retry_policy or {},
            resolved_tasks=draft.task_definitions or [],
            is_active=True,
            spec_checksum=checksum,
            publish_state="publishing",
        )
        db.add(spec)

    db.commit()
    db.refresh(job)
    return _job_out(job, db)


@router.get("/{job_id}/status")
def get_publish_status(
    job_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if not spec:
        return {"state": "draft", "confirmed_at": None}
    try:
        if gateway.dag_exists(spec.dag_id):
            gateway.set_dag_paused(spec.dag_id, job.status != JobStatus.active)
            spec.publish_state = "active"
            if spec.airflow_confirmed_at is None:
                spec.airflow_confirmed_at = _utcnow()
            db.commit()
    except Exception:
        logger.warning("Could not confirm Airflow DAG %s", spec.dag_id, exc_info=True)
    return {
        "state": spec.publish_state,
        "confirmed_at": spec.airflow_confirmed_at,
        "dag_id": spec.dag_id,
    }


@router.get("/{job_id}/version", response_model=JobVersionOut)
def get_version(job_id: str, which: str = Query("published"), db: Session = Depends(get_system_db)):
    """Get published or draft version for a job."""
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    ver = _get_draft_version(job, db) if which == "draft" else _get_published_version(job, db)
    if not ver:
        raise HTTPException(status_code=404, detail=f"No {which} version found")
    return JobVersionOut.model_validate(ver)


# ── Lifecycle actions ─────────────────────────────────────────────────────────

@router.post("/{job_id}/pause", response_model=JobOut)
def pause_job(
    job_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.paused
    job.updated_at = _utcnow()
    # Mark Airflow spec as inactive
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if spec:
        spec.is_active = False
        spec.updated_at = _utcnow()
    db.commit()
    if spec:
        try:
            gateway.set_dag_paused(spec.dag_id, True)
        except Exception:
            logger.warning("Could not immediately pause Airflow DAG %s", spec.dag_id, exc_info=True)
    db.refresh(job)
    return _job_out(job, db)


@router.post("/{job_id}/resume", response_model=JobOut)
def resume_job(
    job_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    published = _get_published_version(job, db)
    if published:
        try:
            missing_targets = missing_notebook_targets(
                published.task_definitions or [],
                workspace_id=str(job.workspace_id) if job.workspace_id else None,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Notebook storage is unavailable.") from exc
        if missing_targets:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot resume job; notebook does not exist: {missing_targets[0]}",
            )
    job.status = JobStatus.active
    job.updated_at = _utcnow()
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if spec:
        spec.is_active = True
        spec.updated_at = _utcnow()
    db.commit()
    if spec:
        try:
            gateway.set_dag_paused(spec.dag_id, False)
        except Exception:
            logger.warning("Could not immediately unpause Airflow DAG %s", spec.dag_id, exc_info=True)
    db.refresh(job)
    return _job_out(job, db)


@router.post("/{job_id}/archive", response_model=JobOut)
def archive_job(job_id: str, db: Session = Depends(get_system_db)):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.archived
    job.updated_at = _utcnow()
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if spec:
        spec.is_active = False
        spec.updated_at = _utcnow()
    db.commit()
    db.refresh(job)
    return _job_out(job, db)


# ── Run triggers ──────────────────────────────────────────────────────────────

@router.post("/{job_id}/run", response_model=JobRunOut, status_code=201)
def trigger_run(
    job_id: str,
    body: RunTriggerIn = RunTriggerIn(),
    current_user: dict = Depends(get_current_user),
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    """
    Trigger a manual run of the job. Creates a JobRun row (queued) and TaskRun
    rows for each task in the published version. Actual Airflow trigger happens
    via the DAG factory — this persists the intent and correlation IDs.
    """
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.current_version is None:
        raise HTTPException(status_code=400, detail="Job has no published version. Publish first.")
    if job.status == JobStatus.archived:
        raise HTTPException(status_code=400, detail="Cannot run an archived job")

    pub = _get_published_version(job, db)
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if not pub or not spec:
        raise HTTPException(status_code=400, detail="Published scheduler specification not found")
    try:
        missing_targets = missing_notebook_targets(
            pub.task_definitions or [],
            workspace_id=str(job.workspace_id) if job.workspace_id else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Notebook storage is unavailable.") from exc
    if missing_targets:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot run job; notebook does not exist: {missing_targets[0]}",
        )
    run, token_refs, task_run_ids = _create_run_records(
        db,
        job,
        pub,
        trigger_type=TriggerType.manual,
        triggered_by=current_user.get("id"),
    )
    try:
        _trigger_scheduler(gateway, spec, run, token_refs, task_run_ids)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Airflow trigger failed for job %s", job.job_id)
        raise HTTPException(status_code=502, detail="Could not start this run. Please retry.") from exc
    db.refresh(run)
    return _job_run_out(run, include_tasks=True)


# ── Runs read endpoints ───────────────────────────────────────────────────────

@router.get("/{job_id}/runs", response_model=List[JobRunOut])
def list_runs(
    job_id: str,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_system_db),
):
    job = db.query(Job).filter(Job.job_id == uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    runs = (
        db.query(JobRun)
        .filter(JobRun.job_id == job.job_id)
        .order_by(JobRun.started_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_job_run_out(r, include_tasks=True) for r in runs]


# ── Job-run level endpoints ───────────────────────────────────────────────────

run_router = APIRouter(
    prefix="/api/v1/job-runs",
    tags=["job-runs"],
    dependencies=[Depends(get_current_user)],
)


@run_router.get("/{run_id}", response_model=JobRunOut)
def get_run(run_id: str, db: Session = Depends(get_system_db)):
    run = db.query(JobRun).filter(JobRun.job_run_id == uuid.UUID(run_id)).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _job_run_out(run, include_tasks=True)


@run_router.post("/{run_id}/cancel", response_model=JobRunOut)
def cancel_run(
    run_id: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    run = db.query(JobRun).filter(JobRun.job_run_id == uuid.UUID(run_id)).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.state not in (RunState.queued, RunState.running):
        raise HTTPException(status_code=400, detail="Run is not in a cancellable state")
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == run.job_id).first()
    if not spec or not run.dag_run_id:
        raise HTTPException(status_code=400, detail="Scheduler run correlation is missing")
    try:
        gateway.cancel_run(spec.dag_id, run.dag_run_id)
    except Exception as exc:
        logger.exception("Airflow cancel failed for run %s", run.job_run_id)
        raise HTTPException(status_code=502, detail="Could not cancel this run.") from exc
    run.state = RunState.cancelled
    run.ended_at = _utcnow()
    run.last_synced_at = _utcnow()
    for tr in run.task_runs:
        if tr.state in (TaskRunState.queued, TaskRunState.running):
            tr.state = TaskRunState.skipped
            tr.ended_at = _utcnow()
    db.commit()
    db.refresh(run)
    return _job_run_out(run, include_tasks=True)


@run_router.post("/{run_id}/rerun", response_model=JobRunOut, status_code=201)
def rerun(
    run_id: str,
    current_user: dict = Depends(get_current_user),
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    """Start a new full run using the current published version of the job."""
    original = db.query(JobRun).filter(JobRun.job_run_id == uuid.UUID(run_id)).first()
    if not original:
        raise HTTPException(status_code=404, detail="Run not found")

    job = db.query(Job).filter(Job.job_id == original.job_id).first()
    if not job or job.current_version is None:
        raise HTTPException(status_code=400, detail="Job has no published version")

    pub = _get_published_version(job, db)
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
    if not pub or not spec:
        raise HTTPException(status_code=400, detail="Published scheduler specification not found")
    new_run, token_refs, task_run_ids = _create_run_records(
        db,
        job,
        pub,
        trigger_type=TriggerType.rerun,
        triggered_by=current_user.get("id"),
        parent_job_run_id=original.job_run_id,
    )
    try:
        _trigger_scheduler(gateway, spec, new_run, token_refs, task_run_ids)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Airflow rerun failed for job %s", job.job_id)
        raise HTTPException(status_code=502, detail="Could not rerun this job.") from exc
    db.refresh(new_run)
    return _job_run_out(new_run, include_tasks=True)


@run_router.post("/{run_id}/tasks/{task_key}/retry", response_model=JobRunOut)
def retry_task(
    run_id: str,
    task_key: str,
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    """
    Retry a specific failed task within a run. Creates a new TaskRun row with
    incremented try_number. Transitions job_run back to running state.
    """
    run = db.query(JobRun).filter(JobRun.job_run_id == uuid.UUID(run_id)).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Find the latest task run for this task_key
    last_tr = (
        db.query(TaskRun)
        .filter(TaskRun.job_run_id == run.job_run_id, TaskRun.task_key == task_key)
        .order_by(TaskRun.try_number.desc())
        .first()
    )
    if not last_tr:
        raise HTTPException(status_code=404, detail="Task not found in this run")
    if last_tr.state not in (TaskRunState.failed, TaskRunState.upstream_failed):
        raise HTTPException(status_code=400, detail="Task is not in a retryable state")

    new_try = TaskRun(
        job_run_id=run.job_run_id,
        task_key=task_key,
        dag_run_id=run.dag_run_id,
        airflow_task_id=last_tr.airflow_task_id or task_key,
        try_number=last_tr.try_number + 1,
        state=TaskRunState.queued,
        last_synced_at=_utcnow(),
    )
    db.add(new_try)
    job = db.query(Job).filter(Job.job_id == run.job_id).first()
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == run.job_id).first()
    if not job or not spec or not run.dag_run_id:
        raise HTTPException(status_code=400, detail="Scheduler correlation is missing")
    mint_execution_token(
        db,
        run,
        task_key,
        user_id=job.owner_user_id,
        workspace_id=job.workspace_id,
    )

    # Re-open the job run state
    if run.state in (RunState.failed,):
        run.state = RunState.running
        run.ended_at = None

    run.last_synced_at = _utcnow()
    try:
        gateway.retry_task(spec.dag_id, run.dag_run_id, last_tr.airflow_task_id or task_key)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Airflow retry failed for task %s", task_key)
        raise HTTPException(status_code=502, detail="Could not retry this task.") from exc
    db.refresh(run)
    return _job_run_out(run, include_tasks=True)


# ── Airflow webhook (internal) ────────────────────────────────────────────────

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
    """
    Webhook called by Airflow callbacks (on_success/on_failure/on_retry).
    Idempotent: keyed on dag_run_id + task_id + try_number + state.
    """
    raw_body = await request.body()
    verify_airflow_signature(raw_body, x_compassx_signature)
    payload = json.loads(raw_body)
    timestamp_raw = payload.get("timestamp")
    try:
        callback_time = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
        if abs((_utcnow() - callback_time).total_seconds()) > 300:
            raise HTTPException(status_code=403, detail="Stale Airflow callback")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid callback timestamp") from exc

    dag_run_id = payload.get("dag_run_id")
    task_key = payload.get("task_id")
    try_number = payload.get("try_number", 1)
    state_str = payload.get("state", "")

    tr = (
        db.query(TaskRun)
        .filter(
            TaskRun.dag_run_id == dag_run_id,
            TaskRun.airflow_task_id == task_key,
            TaskRun.try_number == try_number,
        )
        .first()
    )
    if not tr:
        logger.warning("Webhook: no task_run found for dag_run_id=%s task=%s try=%s", dag_run_id, task_key, try_number)
        return {"status": "not_found"}

    try:
        next_state = TaskRunState(state_str)
    except ValueError:
        return {"status": "unknown_state"}
    tr.state = next_state

    now = _utcnow()
    if state_str == "running" and not tr.started_at:
        tr.started_at = now
    if state_str in ("success", "failed", "skipped", "upstream_failed"):
        tr.ended_at = now
    tr.last_synced_at = now

    # Recompute parent run state
    run = tr.job_run
    if run and run.state != RunState.cancelled:
        latest_by_key = {}
        for task_run in run.task_runs:
            current = latest_by_key.get(task_run.task_key)
            if current is None or task_run.try_number > current.try_number:
                latest_by_key[task_run.task_key] = task_run
        task_states = [task_run.state for task_run in latest_by_key.values()]
        if task_states and all(s == TaskRunState.success for s in task_states):
            run.state = RunState.success
            run.ended_at = now
        elif any(s == TaskRunState.up_for_retry for s in task_states):
            run.state = RunState.up_for_retry
            run.ended_at = None
        elif any(s in (TaskRunState.running, TaskRunState.queued) for s in task_states):
            run.state = RunState.running
            run.started_at = run.started_at or now
            run.ended_at = None
        elif any(s in (TaskRunState.failed, TaskRunState.upstream_failed) for s in task_states):
            run.state = RunState.failed
            run.ended_at = now
        run.last_synced_at = now

    db.commit()
    return {"status": "ok"}
