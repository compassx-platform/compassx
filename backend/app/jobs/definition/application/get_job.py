from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.schemas import JobOut
from app.jobs.shared.support import _authorized_job, _job_out


class GetJob:
    def execute(self, job_id: str, db: Session, guard: Guard) -> JobOut:
        job = _authorized_job(db, guard, job_id, Privilege.BROWSE)
        return _job_out(job, db)


def get_job(job_id, db, guard):
    return GetJob().execute(job_id, db, guard)
