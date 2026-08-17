"""Internal operator protocol and public task execution endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_system_db
from app.dependencies import get_runtime_manager
from app.jobs.execution_service import execute_task, task_executors
from app.jobs.assets import NotebookAssetNotFound, missing_notebook_targets, notebook_assets
from app.jobs.dependencies import get_scheduler_gateway
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, Job, JobStatus
from app.jobs.models.run_trace import (
    ExecutionToken,
    JobExecution,
    JobRun,
    RunState,
    TaskRun,
    TaskRunState,
    TriggerType,
)
from app.jobs.security import (
    generate_execution_token,
    hash_execution_token,
    utcnow,
    verify_internal_secret,
)
from app.jobs.tokens import mint_execution_token

internal_router = APIRouter(prefix="/api/v1/internal", tags=["jobs-internal"])
execution_router = APIRouter(prefix="/api/v1/job-executions", tags=["job-executions"])


class PrepareTaskIn(BaseModel):
    dag_id: str
    dag_run_id: str
    task_key: str
    try_number: int = 1
    token_ref: str | None = None


class TaskExecutionIn(BaseModel):
    task_run_id: uuid.UUID
    task_type: str
    target_ref: str
    parameters: dict = Field(default_factory=dict)


@internal_router.post("/job-tasks/prepare")
def prepare_task(
    body: PrepareTaskIn,
    x_compassx_internal_secret: str | None = Header(None),
    gateway: SchedulerGateway = Depends(get_scheduler_gateway),
    db: Session = Depends(get_system_db),
):
    verify_internal_secret(x_compassx_internal_secret)
    spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.dag_id == body.dag_id).first()
    if not spec:
        raise HTTPException(status_code=404, detail="Job specification not found")
    job = db.query(Job).filter(Job.job_id == spec.job_id).first()
    if not spec.is_active or not job or job.status != JobStatus.active:
        raise HTTPException(status_code=409, detail="Job is paused or inactive")
    try:
        missing_targets = missing_notebook_targets(
            spec.resolved_tasks or [],
            workspace_id=str(spec.workspace_id) if spec.workspace_id else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Notebook storage is unavailable.") from exc
    if missing_targets:
        spec.is_active = False
        job.status = JobStatus.paused
        job.updated_at = utcnow()
        db.commit()
        try:
            gateway.set_dag_paused(spec.dag_id, True)
        except Exception:
            pass
        raise HTTPException(
            status_code=409,
            detail=f"Job was paused because its notebook does not exist: {missing_targets[0]}",
        )
    run = db.query(JobRun).filter(JobRun.dag_run_id == body.dag_run_id).first()
    if run is None:
        run = JobRun(
            job_id=spec.job_id,
            job_version=spec.job_version,
            dag_run_id=body.dag_run_id,
            trigger_type=TriggerType.scheduled,
            state=RunState.running,
            started_at=utcnow(),
            last_synced_at=utcnow(),
        )
        db.add(run)
        db.flush()
        for task_spec in spec.resolved_tasks or []:
            db.add(TaskRun(
                job_run_id=run.job_run_id,
                task_key=task_spec["task_key"],
                dag_run_id=body.dag_run_id,
                airflow_task_id=task_spec["task_key"],
                try_number=1,
                state=TaskRunState.queued,
                last_synced_at=utcnow(),
            ))
        db.flush()
    task_run = db.query(TaskRun).filter(
        TaskRun.dag_run_id == body.dag_run_id,
        TaskRun.airflow_task_id == body.task_key,
        TaskRun.try_number == body.try_number,
    ).first()
    if task_run is None:
        task_run = TaskRun(
            job_run_id=run.job_run_id,
            task_key=body.task_key,
            dag_run_id=body.dag_run_id,
            airflow_task_id=body.task_key,
            try_number=body.try_number,
            state=TaskRunState.running,
            started_at=utcnow(),
            last_synced_at=utcnow(),
        )
        db.add(task_run)
        db.flush()
    else:
        task_run.state = TaskRunState.running
        task_run.started_at = task_run.started_at or utcnow()
        task_run.last_synced_at = utcnow()
    run.state = RunState.running
    run.started_at = run.started_at or utcnow()
    run.last_synced_at = utcnow()

    token = None
    if body.token_ref:
        try:
            token = db.query(ExecutionToken).filter(
                ExecutionToken.token_id == uuid.UUID(body.token_ref),
                ExecutionToken.job_run_id == run.job_run_id,
                ExecutionToken.task_key == body.task_key,
                ExecutionToken.exchanged_at.is_(None),
                ExecutionToken.expires_at > utcnow(),
            ).first()
        except ValueError:
            token = None
    if token is None:
        token = db.query(ExecutionToken).filter(
            ExecutionToken.job_run_id == run.job_run_id,
            ExecutionToken.task_key == body.task_key,
            ExecutionToken.exchanged_at.is_(None),
            ExecutionToken.expires_at > utcnow(),
        ).order_by(ExecutionToken.created_at.desc()).first()
    if token is None:
        token = mint_execution_token(
            db,
            run,
            body.task_key,
            user_id=job.owner_user_id if job else None,
            workspace_id=job.workspace_id if job else None,
        )
    db.commit()
    return {"task_run_id": str(task_run.task_run_id), "token_ref": str(token.token_id)}


@internal_router.post("/execution-tokens/{token_ref}/exchange")
def exchange_token(
    token_ref: str,
    x_compassx_internal_secret: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    verify_internal_secret(x_compassx_internal_secret)
    try:
        token_id = uuid.UUID(token_ref)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Execution token not found") from exc
    token = db.query(ExecutionToken).filter(
        ExecutionToken.token_id == token_id
    ).with_for_update().first()
    if not token:
        raise HTTPException(status_code=404, detail="Execution token not found")
    if token.exchanged_at is not None or token.expires_at <= utcnow():
        raise HTTPException(status_code=410, detail="Execution token is expired or already exchanged")
    raw, token_hash = generate_execution_token()
    token.token_hash = token_hash
    token.exchanged_at = utcnow()
    db.commit()
    return {"access_token": raw, "expires_at": token.expires_at}


@execution_router.post("/run", status_code=202)
def run_task(
    body: TaskExecutionIn,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing execution token")
    raw = authorization.split(" ", 1)[1]
    token = db.query(ExecutionToken).filter(
        ExecutionToken.token_hash == hash_execution_token(raw)
    ).with_for_update().first()
    if not token or token.expires_at <= utcnow():
        raise HTTPException(status_code=403, detail="Invalid or expired execution token")
    task_run = db.query(TaskRun).filter(TaskRun.task_run_id == body.task_run_id).first()
    if not task_run or task_run.job_run_id != token.job_run_id or task_run.task_key != token.task_key:
        raise HTTPException(status_code=403, detail="Execution token scope mismatch")
    existing = db.query(JobExecution).filter(
        JobExecution.task_run_id == task_run.task_run_id
    ).first()
    if existing is not None:
        return {"execution_ref": str(existing.execution_id), "state": existing.state}
    if token.used_at is not None:
        raise HTTPException(status_code=403, detail="Execution token was already used")

    job_run = db.query(JobRun).filter(JobRun.job_run_id == task_run.job_run_id).first()
    spec = db.query(AirflowJobSpec).filter(
        AirflowJobSpec.job_id == job_run.job_id,
        AirflowJobSpec.job_version == job_run.job_version,
    ).first() if job_run else None
    task_spec = next(
        (item for item in (spec.resolved_tasks or []) if item.get("task_key") == task_run.task_key),
        None,
    ) if spec else None
    normalized_requested = body.target_ref.lstrip("/").replace("\\", "/")
    normalized_scoped = str((task_spec or {}).get("target_ref") or "").lstrip("/").replace("\\", "/")
    if not task_spec or task_spec.get("task_type") != body.task_type or normalized_requested != normalized_scoped:
        raise HTTPException(status_code=403, detail="Execution token is not scoped to this task target")
    try:
        task_executors.get(body.task_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    token.used_at = utcnow()
    execution = JobExecution(task_run_id=task_run.task_run_id, state="queued")
    db.add(execution)
    db.flush()
    task_run.execution_ref = str(execution.execution_id)
    db.commit()
    runtime_manager = get_runtime_manager(request)
    background_tasks.add_task(
        execute_task,
        str(execution.execution_id),
        task_type=body.task_type,
        target_ref=body.target_ref,
        parameters=body.parameters,
        user_id=token.scoped_user_id or "",
        workspace_id=str(token.scoped_workspace_id or ""),
        access_token=raw,
        runtime_manager=runtime_manager,
    )
    return {"execution_ref": str(execution.execution_id), "state": "queued"}


@execution_router.get("/{execution_id}/notebook")
async def download_execution_notebook(
    execution_id: str,
    authorization: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    """Stream the task's catalog-resolved notebook to its ephemeral runtime."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing execution token")
    raw = authorization.split(" ", 1)[1]
    token = db.query(ExecutionToken).filter(
        ExecutionToken.token_hash == hash_execution_token(raw),
        ExecutionToken.expires_at > utcnow(),
    ).first()
    try:
        execution_uuid = uuid.UUID(execution_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    execution = db.query(JobExecution).filter(
        JobExecution.execution_id == execution_uuid
    ).first()
    task_run = db.query(TaskRun).filter(
        TaskRun.task_run_id == execution.task_run_id
    ).first() if execution else None
    if not token or not task_run or token.job_run_id != task_run.job_run_id or token.task_key != task_run.task_key:
        raise HTTPException(status_code=403, detail="Execution token scope mismatch")
    job_run = db.query(JobRun).filter(JobRun.job_run_id == task_run.job_run_id).first()
    spec = db.query(AirflowJobSpec).filter(
        AirflowJobSpec.job_id == job_run.job_id,
        AirflowJobSpec.job_version == job_run.job_version,
    ).first() if job_run else None
    task_spec = next(
        (item for item in (spec.resolved_tasks or []) if item.get("task_key") == task_run.task_key),
        None,
    ) if spec else None
    if not task_spec or task_spec.get("task_type") != "notebook":
        raise HTTPException(status_code=404, detail="Notebook task specification not found")
    try:
        content = await notebook_assets.read(
            str(task_spec["target_ref"]),
            workspace_id=str(spec.workspace_id) if spec.workspace_id else None,
        )
    except NotebookAssetNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type="application/x-ipynb+json")


@internal_router.get("/job-executions/{execution_id}")
def execution_status(
    execution_id: str,
    x_compassx_internal_secret: str | None = Header(None),
    db: Session = Depends(get_system_db),
):
    verify_internal_secret(x_compassx_internal_secret)
    execution = db.query(JobExecution).filter(
        JobExecution.execution_id == uuid.UUID(execution_id)
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "execution_ref": str(execution.execution_id),
        "state": execution.state,
        "output_uri": execution.output_uri,
        "error": execution.error,
    }
