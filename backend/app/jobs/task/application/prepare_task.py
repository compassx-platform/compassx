import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.jobs.assets import missing_notebook_targets
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, Job, JobStatus
from app.jobs.models.run_trace import (
    ExecutionToken,
    JobRun,
    RunState,
    TaskRun,
    TaskRunState,
    TriggerType,
)
from app.jobs.security import utcnow, verify_internal_secret
from app.jobs.tokens import mint_execution_token


class PrepareTask:
    def execute(self, body, secret: str | None, gateway: SchedulerGateway, db: Session):
        verify_internal_secret(secret)
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


def prepare_task(body, secret, gateway, db):
    return PrepareTask().execute(body, secret, gateway, db)
