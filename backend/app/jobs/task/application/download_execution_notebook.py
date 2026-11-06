import uuid

from fastapi import HTTPException, Response
from sqlalchemy.orm import Session

from app.jobs.assets import NotebookAssetNotFound, notebook_assets
from app.jobs.models.job import AirflowJobSpec
from app.jobs.models.run_trace import ExecutionToken, JobExecution, JobRun, TaskRun
from app.jobs.security import hash_execution_token, utcnow


class DownloadExecutionNotebook:
    async def execute(self, execution_id: str, authorization: str | None, db: Session):
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


def download_execution_notebook(execution_id, authorization, db):
    return DownloadExecutionNotebook().execute(execution_id, authorization, db)
