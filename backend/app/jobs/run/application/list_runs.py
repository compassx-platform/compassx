from typing import List

from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.models.run_trace import JobRun
from app.jobs.schemas import JobRunOut
from app.jobs.shared.support import _authorized_job, _job_run_out


class ListRuns:
    def execute(self, job_id: str, limit: int, offset: int, db: Session, guard: Guard) -> List[JobRunOut]:
        job = _authorized_job(db, guard, job_id, Privilege.BROWSE)
        runs = (
            db.query(JobRun)
            .filter(JobRun.job_id == job.job_id)
            .order_by(JobRun.started_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_job_run_out(r, include_tasks=True) for r in runs]


def list_runs(job_id, limit, offset, db, guard):
    return ListRuns().execute(job_id, limit, offset, db, guard)
