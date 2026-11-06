from sqlalchemy import func
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.models.job import JobVersion
from app.jobs.schemas import DraftUpdate, JobVersionOut
from app.jobs.shared.support import _authorized_job, _utcnow


class SaveDraft:
    def execute(self, job_id: str, body: DraftUpdate, db: Session, guard: Guard) -> JobVersionOut:
        """
        Autosave the draft version for a job.
        Creates a new draft version if none exists, or updates the existing one.
        """
        job = _authorized_job(db, guard, job_id, Privilege.EDIT)

        # Versions are immutable snapshots. Every explicit save appends a row and
        # moves the draft pointer; prior drafts remain available for audit.
        latest_version = (
            db.query(func.max(JobVersion.version_number))
            .filter(JobVersion.job_id == job.job_id)
            .scalar()
            or 0
        )
        draft = JobVersion(
            job_id=job.job_id,
            version_number=latest_version + 1,
            schedule_cron=body.schedule_cron,
            timezone=body.timezone,
            max_active_runs=body.max_active_runs,
            retry_policy=body.retry_policy.model_dump(),
            task_definitions=[t.model_dump() for t in body.task_definitions],
            is_published=False,
            created_by=guard.principal.id,
        )
        db.add(draft)
        db.flush()
        job.draft_version = draft.version_number
        job.updated_at = _utcnow()
        db.commit()
        db.refresh(draft)
        return JobVersionOut.model_validate(draft)


def save_draft(job_id, body, db, guard):
    return SaveDraft().execute(job_id, body, db, guard)
