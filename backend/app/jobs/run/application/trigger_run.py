from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.assets import missing_notebook_targets
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, JobStatus
from app.jobs.models.run_trace import TriggerType
from app.jobs.schemas import JobRunOut, RunTriggerIn
from app.jobs.shared.support import (
    _authorized_job,
    _create_run_records,
    _get_published_version,
    _job_run_out,
    _trigger_scheduler,
    logger,
)


class TriggerRun:
    def execute(
        self,
        job_id: str,
        body: RunTriggerIn,
        gateway: SchedulerGateway,
        db: Session,
        guard: Guard,
    ) -> JobRunOut:
        """
        Trigger a manual run of the job. Creates a JobRun row (queued) and TaskRun
        rows for each task in the published version. Actual Airflow trigger happens
        via the DAG factory — this persists the intent and correlation IDs.
        """
        # Tasks execute under a token minted for ``job.owner_user_id`` (see
        # _create_run_records), so EXECUTE on a job is a delegation of the owner's
        # data access, not merely permission to press a button. It is granted
        # deliberately and never inferred from BROWSE.
        job = _authorized_job(db, guard, job_id, Privilege.EXECUTE)
        if job.current_version is None:
            raise HTTPException(status_code=400, detail="Job has no published version. Publish first.")
        if job.status == JobStatus.archived:
            raise HTTPException(status_code=400, detail="Cannot run an archived job")

        pub = _get_published_version(job, db)
        spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
        if not pub or not spec:
            raise HTTPException(status_code=400, detail="Published scheduler specification not found")
        try:
            missing_targets = missing_notebook_targets(
                pub.task_definitions or [],
                workspace_id=str(job.workspace_id) if job.workspace_id else None,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Notebook storage is unavailable.") from exc
        if missing_targets:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot run job; notebook does not exist: {missing_targets[0]}",
            )
        run, token_refs, task_run_ids = _create_run_records(
            db,
            job,
            pub,
            trigger_type=TriggerType.manual,
            triggered_by=guard.principal.id,
        )
        try:
            _trigger_scheduler(gateway, spec, run, token_refs, task_run_ids)
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.exception("Airflow trigger failed for job %s", job.job_id)
            raise HTTPException(status_code=502, detail="Could not start this run. Please retry.") from exc
        db.refresh(run)
        return _job_run_out(run, include_tasks=True)


def trigger_run(job_id, body, gateway, db, guard):
    return TriggerRun().execute(job_id, body, gateway, db, guard)
