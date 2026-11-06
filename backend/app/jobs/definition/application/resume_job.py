from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.assets import missing_notebook_targets
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, JobStatus
from app.jobs.schemas import JobOut
from app.jobs.shared.support import _authorized_job, _get_published_version, _job_out, _utcnow, logger


class ResumeJob:
    def execute(self, job_id: str, gateway: SchedulerGateway, db: Session, guard: Guard) -> JobOut:
        # Resuming puts the job back on its schedule, where every future run acts
        # as the owner. Same bar as pausing.
        job = _authorized_job(db, guard, job_id, Privilege.EDIT)
        published = _get_published_version(job, db)
        if published:
            try:
                missing_targets = missing_notebook_targets(
                    published.task_definitions or [],
                    workspace_id=str(job.workspace_id) if job.workspace_id else None,
                )
            except Exception as exc:
                raise HTTPException(status_code=503, detail="Notebook storage is unavailable.") from exc
            if missing_targets:
                raise HTTPException(
                    status_code=422,
                    detail=f"Cannot resume job; notebook does not exist: {missing_targets[0]}",
                )
        job.status = JobStatus.active
        job.updated_at = _utcnow()
        spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
        if spec:
            spec.is_active = True
            spec.updated_at = _utcnow()
        db.commit()
        if spec:
            try:
                gateway.set_dag_paused(spec.dag_id, False)
            except Exception:
                logger.warning("Could not immediately unpause Airflow DAG %s", spec.dag_id, exc_info=True)
        db.refresh(job)
        return _job_out(job, db)


def resume_job(job_id, gateway, db, guard):
    return ResumeJob().execute(job_id, gateway, db, guard)
