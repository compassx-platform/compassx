import hashlib
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.assets import missing_notebook_targets
from app.jobs.execution_service import task_executors
from app.jobs.models.job import AirflowJobSpec, JobStatus
from app.jobs.schemas import JobOut
from app.jobs.shared.support import _authorized_job, _get_draft_version, _job_out, _utcnow
from app.jobs.validation import validate_job_spec


class PublishJob:
    def execute(self, job_id: str, db: Session, guard: Guard) -> JobOut:
        """
        Publish the current draft: mark it published, update current_version pointer,
        upsert airflow_job_specs for DAG factory consumption.
        """
        job = _authorized_job(db, guard, job_id, Privilege.EDIT)
        if job.draft_version is None:
            raise HTTPException(status_code=400, detail="No draft version to publish")

        draft = _get_draft_version(job, db)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft version not found")
        validate_job_spec(draft.schedule_cron, draft.task_definitions or [])
        for task in draft.task_definitions or []:
            if task.get("task_type") not in task_executors.registered_types():
                raise HTTPException(
                    status_code=422,
                    detail=f"No local-dev execution adapter is available for task type: {task.get('task_type')}",
                )
        try:
            missing_targets = missing_notebook_targets(
                draft.task_definitions or [],
                workspace_id=str(job.workspace_id) if job.workspace_id else None,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Notebook storage is unavailable; publishing cannot be validated.",
            ) from exc
        if missing_targets:
            raise HTTPException(
                status_code=422,
                detail=f"Notebook does not exist: {missing_targets[0]}",
            )

        # Mark published
        draft.is_published = True
        draft.published_at = _utcnow()
        draft.published_by = guard.principal.id

        # Promote
        job.current_version = draft.version_number
        job.draft_version = None
        job.status = JobStatus.active
        job.updated_at = _utcnow()

        # Upsert airflow_job_specs
        dag_id = f"compassx_job_{job.job_id}"
        spec_payload = {
            "dag_id": dag_id,
            "schedule_cron": draft.schedule_cron,
            "timezone": draft.timezone,
            "max_active_runs": draft.max_active_runs,
            "retry_policy": draft.retry_policy,
            "resolved_tasks": draft.task_definitions,
            "workspace_id": str(job.workspace_id) if job.workspace_id else None,
        }
        checksum = hashlib.md5(json.dumps(spec_payload, sort_keys=True).encode()).hexdigest()

        existing_spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
        if existing_spec:
            existing_spec.dag_id = dag_id
            existing_spec.job_version = draft.version_number
            existing_spec.workspace_id = job.workspace_id
            existing_spec.schedule_cron = draft.schedule_cron
            existing_spec.timezone = draft.timezone
            existing_spec.max_active_runs = draft.max_active_runs
            existing_spec.retry_policy = draft.retry_policy or {}
            existing_spec.resolved_tasks = draft.task_definitions or []
            existing_spec.is_active = True
            existing_spec.spec_checksum = checksum
            existing_spec.publish_state = "publishing"
            existing_spec.airflow_confirmed_at = None
            existing_spec.updated_at = _utcnow()
        else:
            spec = AirflowJobSpec(
                job_id=job.job_id,
                dag_id=dag_id,
                job_version=draft.version_number,
                workspace_id=job.workspace_id,
                schedule_cron=draft.schedule_cron,
                timezone=draft.timezone,
                max_active_runs=draft.max_active_runs,
                retry_policy=draft.retry_policy or {},
                resolved_tasks=draft.task_definitions or [],
                is_active=True,
                spec_checksum=checksum,
                publish_state="publishing",
            )
            db.add(spec)

        db.commit()
        db.refresh(job)
        return _job_out(job, db)


def publish_job(job_id, db, guard):
    return PublishJob().execute(job_id, db, guard)
