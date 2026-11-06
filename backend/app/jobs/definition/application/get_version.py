from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.schemas import JobVersionOut
from app.jobs.shared.support import _authorized_job, _get_draft_version, _get_published_version


class GetVersion:
    def execute(self, job_id: str, which: str, db: Session, guard: Guard) -> JobVersionOut:
        """Get published or draft version for a job."""
        job = _authorized_job(db, guard, job_id, Privilege.BROWSE)
        ver = _get_draft_version(job, db) if which == "draft" else _get_published_version(job, db)
        if not ver:
            raise HTTPException(status_code=404, detail=f"No {which} version found")
        return JobVersionOut.model_validate(ver)


def get_version(job_id, which, db, guard):
    return GetVersion().execute(job_id, which, db, guard)
