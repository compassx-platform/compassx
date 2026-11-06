from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.schemas import JobOut, JobUpdate
from app.jobs.shared.support import _authorized_job, _job_out, _utcnow


class UpdateJob:
    def execute(self, job_id: str, body: JobUpdate, db: Session, guard: Guard) -> JobOut:
        job = _authorized_job(db, guard, job_id, Privilege.EDIT)
        if body.name is not None:
            job.name = body.name
        if body.description is not None:
            job.description = body.description
        job.updated_at = _utcnow()
        db.commit()
        db.refresh(job)
        return _job_out(job, db)


def update_job(job_id, body, db, guard):
    return UpdateJob().execute(job_id, body, db, guard)
