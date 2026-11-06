"""Shared job lookups, run rows, and response mapping.

Logger name stays ``app.jobs.routes`` for messages that moved with these helpers.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, Job, JobVersion
from app.jobs.models.run_trace import JobRun, RunState, TaskRun, TaskRunState, TriggerType
from app.jobs.schemas import JobOut, JobRunOut, TaskRunOut
from app.jobs.tokens import mint_execution_token

logger = logging.getLogger("app.jobs.routes")


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


def _job_id(raw: str) -> uuid.UUID:
    """Parse a job or run id, treating a malformed one as absent.

    ``uuid.UUID(raw)`` on a non-uuid string raises ValueError, which FastAPI
    turns into a 500. A caller probing with garbage should get the same answer
    as one probing with a well-formed id that does not exist.
    """
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail="Job not found")


def _authorized_job(db: Session, guard: Guard, job_id: str, privilege: Privilege) -> Job:
    """Load a job the caller holds ``privilege`` on, or raise.

    Scoped to the guard's workspace before the grant check, so a job id from
    another workspace is simply not found — a grant in workspace A must never
    be evaluated against an object in workspace B.
    """
    job = (
        db.query(Job)
        .filter(
            Job.job_id == _job_id(job_id),
            Job.workspace_id == uuid.UUID(guard.workspace_id),
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    guard.require(privilege, Securable.job(str(job.job_id)))
    return job


def _authorized_run(
    db: Session, guard: Guard, run_id: str, privilege: Privilege
) -> tuple[JobRun, Job]:
    """Load a run, and the job that owns it, after checking access to the job.

    Runs carry no grants of their own: a run is an execution of a job, so the
    job is the securable. Resolving the parent first is also what scopes the
    lookup — ``JobRun.job_run_id`` is globally unique, so an unscoped query
    would happily return a run belonging to another workspace.
    """
    run = db.query(JobRun).filter(JobRun.job_run_id == _job_id(run_id)).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    job = (
        db.query(Job)
        .filter(
            Job.job_id == run.job_id,
            Job.workspace_id == uuid.UUID(guard.workspace_id),
        )
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Run not found")
    guard.require(privilege, Securable.job(str(job.job_id)))
    return run, job
