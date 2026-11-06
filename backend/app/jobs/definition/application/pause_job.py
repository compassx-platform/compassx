from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, JobStatus
from app.jobs.schemas import JobOut
from app.jobs.shared.support import _authorized_job, _job_out, _utcnow, logger


class PauseJob:
    def execute(self, job_id: str, gateway: SchedulerGateway, db: Session, guard: Guard) -> JobOut:
        # Pausing stops the schedule for everyone who depends on this job's
        # output. That is a change to the job, not a run of it, so EDIT.
        job = _authorized_job(db, guard, job_id, Privilege.EDIT)
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


def pause_job(job_id, gateway, db, guard):
    return PauseJob().execute(job_id, gateway, db, guard)
