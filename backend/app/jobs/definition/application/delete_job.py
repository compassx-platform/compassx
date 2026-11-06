from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.shared.support import _authorized_job


class DeleteJob:
    def execute(self, job_id: str, db: Session, guard: Guard) -> None:
        # Deleting takes the run history with it, and cannot be undone by whoever
        # was relying on the schedule — so MANAGE, not EDIT.
        job = _authorized_job(db, guard, job_id, Privilege.MANAGE)
        db.delete(job)
        db.commit()


def delete_job(job_id, db, guard):
    return DeleteJob().execute(job_id, db, guard)
