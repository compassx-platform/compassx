from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec
from app.jobs.models.run_trace import TriggerType
from app.jobs.schemas import JobRunOut
from app.jobs.shared.support import (
    _authorized_run,
    _create_run_records,
    _get_published_version,
    _job_run_out,
    _trigger_scheduler,
    logger,
)


class Rerun:
    def execute(self, run_id: str, gateway: SchedulerGateway, db: Session, guard: Guard) -> JobRunOut:
        """Start a new full run using the current published version of the job."""
        original, job = _authorized_run(db, guard, run_id, Privilege.EXECUTE)
        if job.current_version is None:
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
            triggered_by=guard.principal.id,
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


def rerun(run_id, gateway, db, guard):
    return Rerun().execute(run_id, gateway, db, guard)
