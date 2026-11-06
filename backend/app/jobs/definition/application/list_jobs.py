from typing import List, Optional

from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable
from app.jobs.models.job import Job, JobStatus
from app.jobs.schemas import JobOut
from app.jobs.shared.support import _job_out
import uuid


class ListJobs:
    def execute(
        self,
        search: Optional[str],
        status: Optional[str],
        db: Session,
        guard: Guard,
    ) -> List[JobOut]:
        """List the jobs in this workspace that the caller may browse."""
        # The workspace comes from the resolved request context. It used to be a
        # ``workspace_id`` query parameter, which meant a caller could name any
        # workspace — and omitting it returned every job on the deployment.
        q = db.query(Job).filter(Job.workspace_id == uuid.UUID(guard.workspace_id))
        if status:
            try:
                q = q.filter(Job.status == JobStatus(status))
            except ValueError:
                pass
        if search:
            q = q.filter(Job.name.ilike(f"%{search}%"))
        jobs = q.order_by(Job.updated_at.desc()).all()
        visible = guard.filter(
            Privilege.BROWSE, jobs, lambda j: Securable.job(str(j.job_id))
        )
        return [_job_out(j, db) for j in visible]


def list_jobs(search, status, db, guard):
    return ListJobs().execute(search, status, db, guard)
