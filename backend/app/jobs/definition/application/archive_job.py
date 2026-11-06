from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.models.job import AirflowJobSpec, JobStatus
from app.jobs.schemas import JobOut
from app.jobs.shared.support import _authorized_job, _job_out, _utcnow


class ArchiveJob:
    def execute(self, job_id: str, db: Session, guard: Guard) -> JobOut:
        # Archiving retires the job permanently as far as the UI is concerned;
        # closer to deletion than to pausing, so MANAGE.
        job = _authorized_job(db, guard, job_id, Privilege.MANAGE)
        job.status = JobStatus.archived
        job.updated_at = _utcnow()
        spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
        if spec:
            spec.is_active = False
            spec.updated_at = _utcnow()
        db.commit()
        db.refresh(job)
        return _job_out(job, db)


def archive_job(job_id, db, guard):
    return ArchiveJob().execute(job_id, db, guard)
