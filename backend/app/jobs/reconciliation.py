"""Poll-based Airflow reconciliation safety net."""

from __future__ import annotations

import logging

from app.database import SystemSessionLocal
from app.jobs.models.job import AirflowJobSpec
from app.jobs.models.run_trace import (
    JobRun,
    RunState,
    SyncCorrection,
    TaskRun,
    TaskRunState,
)
from app.jobs.security import utcnow

logger = logging.getLogger(__name__)

_RUN_STATES = {
    "queued": RunState.queued,
    "running": RunState.running,
    "success": RunState.success,
    "failed": RunState.failed,
}
_TASK_STATES = {
    "queued": TaskRunState.queued,
    "scheduled": TaskRunState.queued,
    "running": TaskRunState.running,
    "success": TaskRunState.success,
    "failed": TaskRunState.failed,
    "up_for_retry": TaskRunState.up_for_retry,
    "upstream_failed": TaskRunState.upstream_failed,
    "skipped": TaskRunState.skipped,
}


def reconcile_airflow_runs(gateway) -> int:
    db = SystemSessionLocal()
    corrections = 0
    try:
        runs = db.query(JobRun).filter(
            JobRun.state.in_([RunState.queued, RunState.running, RunState.up_for_retry])
        ).all()
        for run in runs:
            spec = db.query(AirflowJobSpec).filter(
                AirflowJobSpec.job_id == run.job_id
            ).first()
            if not spec or not run.dag_run_id:
                continue
            try:
                airflow_run = gateway.get_run(spec.dag_id, run.dag_run_id)
                next_run_state = _RUN_STATES.get(airflow_run.get("state"))
                if next_run_state and run.state != next_run_state:
                    db.add(SyncCorrection(
                        job_run_id=run.job_run_id,
                        previous_state=run.state.value,
                        corrected_state=next_run_state.value,
                    ))
                    run.state = next_run_state
                    corrections += 1
                for airflow_task in gateway.get_task_instances(spec.dag_id, run.dag_run_id):
                    task = db.query(TaskRun).filter(
                        TaskRun.dag_run_id == run.dag_run_id,
                        TaskRun.airflow_task_id == airflow_task.get("task_id"),
                        TaskRun.try_number == max(int(airflow_task.get("try_number") or 1), 1),
                    ).first()
                    next_task_state = _TASK_STATES.get(airflow_task.get("state"))
                    if task and next_task_state:
                        now = utcnow()
                        if task.state != next_task_state:
                            db.add(SyncCorrection(
                                job_run_id=run.job_run_id,
                                task_run_id=task.task_run_id,
                                previous_state=task.state.value,
                                corrected_state=next_task_state.value,
                            ))
                            task.state = next_task_state
                            corrections += 1
                        if next_task_state == TaskRunState.running:
                            task.started_at = task.started_at or now
                        if next_task_state in (
                            TaskRunState.success,
                            TaskRunState.failed,
                            TaskRunState.upstream_failed,
                            TaskRunState.skipped,
                        ):
                            task.ended_at = task.ended_at or now
                        task.last_synced_at = now
                run.last_synced_at = utcnow()
                if run.state in (RunState.success, RunState.failed, RunState.cancelled):
                    run.ended_at = run.ended_at or utcnow()
                elif run.state == RunState.running:
                    run.started_at = run.started_at or utcnow()
            except Exception:
                logger.warning("Could not reconcile Airflow run %s", run.job_run_id, exc_info=True)
        db.commit()
        return corrections
    finally:
        db.close()
