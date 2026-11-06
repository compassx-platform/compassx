import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.jobs.models.job import Job, JobStatus, JobVersion
from app.jobs.schemas import JobCreate, JobOut
from app.jobs.shared.support import _job_out
from app.governance.securable import Securable


def _ensure_schema(db: Session) -> None:
    """Create the jobs schema if it doesn't exist (idempotent, called at request time)."""
    try:
        db.execute(text("CREATE SCHEMA IF NOT EXISTS jobs"))
        db.commit()
    except Exception:
        db.rollback()


class CreateJob:
    def execute(self, body: JobCreate, db: Session, guard: Guard) -> JobOut:
        """Create a new job with an initial empty draft version."""
        # A job has no parent securable to hold CREATE on, and a published job
        # runs on a schedule with its owner's identity, so creation sits with the
        # workspace admin rather than being open to every member.
        guard.require_workspace_admin("Creating a job")
        _ensure_schema(db)
        job = Job(
            name=body.name,
            description=body.description,
            # Taken from the resolved workspace, never from the body: accepting
            # ``body.workspace_id`` let a caller plant a job in a workspace they
            # have no access to, where it would then run on a schedule.
            workspace_id=uuid.UUID(guard.workspace_id),
            owner_user_id=guard.principal.id,
            status=JobStatus.active,
            current_version=None,
            draft_version=None,
        )
        db.add(job)
        db.flush()

        # Create version 1 as draft
        ver = JobVersion(
            job_id=job.job_id,
            version_number=1,
            is_published=False,
            task_definitions=[],
            retry_policy={},
            created_by=guard.principal.id,
        )
        db.add(ver)
        db.flush()
        job.draft_version = 1
        guard.claim_ownership(Securable.job(str(job.job_id)))
        db.commit()
        db.refresh(job)
        return _job_out(job, db)


def create_job(body, db, guard):
    return CreateJob().execute(body, db, guard)
