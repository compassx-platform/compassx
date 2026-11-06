from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec
from app.jobs.models.run_trace import RunState, TaskRunState
from app.jobs.schemas import JobRunOut
from app.jobs.shared.support import _authorized_run, _job_run_out, _utcnow, logger


class CancelRun:
    def execute(self, run_id: str, gateway: SchedulerGateway, db: Session, guard: Guard) -> JobRunOut:
        # Whoever may start a run may stop one — a runaway job that only its
        # owner can kill is worse than a cancelled run.
        run, _ = _authorized_run(db, guard, run_id, Privilege.EXECUTE)
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


def cancel_run(run_id, gateway, db, guard):
    return CancelRun().execute(run_id, gateway, db, guard)
