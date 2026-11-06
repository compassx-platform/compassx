from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.schemas import JobRunOut
from app.jobs.shared.support import _authorized_run, _job_run_out


class GetRun:
    def execute(self, run_id: str, db: Session, guard: Guard) -> JobRunOut:
        run, _ = _authorized_run(db, guard, run_id, Privilege.BROWSE)
        return _job_run_out(run, include_tasks=True)


def get_run(run_id, db, guard):
    return GetRun().execute(run_id, db, guard)
