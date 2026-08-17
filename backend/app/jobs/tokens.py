"""Execution-token lifecycle owned by the Jobs application layer."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.jobs.models.run_trace import ExecutionToken, JobRun
from services.airflow.config import airflow_settings
from app.jobs.security import utcnow


def mint_execution_token(
    db: Session,
    run: JobRun,
    task_key: str,
    *,
    user_id: str | None,
    workspace_id,
) -> ExecutionToken:
    token = ExecutionToken(
        job_run_id=run.job_run_id,
        task_key=task_key,
        scoped_user_id=user_id,
        scoped_workspace_id=workspace_id,
        expires_at=utcnow() + timedelta(
            seconds=airflow_settings.AIRFLOW_EXECUTION_TOKEN_TTL_SECONDS
        ),
    )
    db.add(token)
    db.flush()
    return token
