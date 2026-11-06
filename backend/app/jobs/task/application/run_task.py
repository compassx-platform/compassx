from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.dependencies import get_runtime_manager
from app.jobs.execution_service import execute_task, task_executors
from app.jobs.models.job import AirflowJobSpec
from app.jobs.models.run_trace import ExecutionToken, JobExecution, JobRun, TaskRun
from app.jobs.security import hash_execution_token, utcnow


class RunTask:
    def execute(self, body, request: Request, background_tasks, authorization: str | None, db: Session):
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


def run_task(body, request, background_tasks, authorization, db):
    return RunTask().execute(body, request, background_tasks, authorization, db)
