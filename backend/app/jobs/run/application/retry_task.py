from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec
from app.jobs.models.run_trace import RunState, TaskRun, TaskRunState
from app.jobs.schemas import JobRunOut
from app.jobs.shared.support import _authorized_run, _job_run_out, _utcnow, logger
from app.jobs.tokens import mint_execution_token


class RetryTask:
    def execute(
        self,
        run_id: str,
        task_key: str,
        gateway: SchedulerGateway,
        db: Session,
        guard: Guard,
    ) -> JobRunOut:
        """
        Retry a specific failed task within a run. Creates a new TaskRun row with
        incremented try_number. Transitions job_run back to running state.
        """
        # Mints a fresh execution token as the job owner, exactly as a manual
        # trigger does, so it takes the same privilege.
        run, job = _authorized_run(db, guard, run_id, Privilege.EXECUTE)

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
        spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == run.job_id).first()
        if not spec or not run.dag_run_id:
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


def retry_task(run_id, task_key, gateway, db, guard):
    return RetryTask().execute(run_id, task_key, gateway, db, guard)
