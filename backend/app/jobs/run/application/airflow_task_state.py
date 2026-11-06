import json
from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.jobs.models.run_trace import RunState, TaskRun, TaskRunState
from app.jobs.security import verify_airflow_signature
from app.jobs.shared.support import _utcnow, logger


class AirflowTaskState:
    async def execute(self, request: Request, signature: str | None, db: Session):
        """
        Webhook called by Airflow callbacks (on_success/on_failure/on_retry).
        Idempotent: keyed on dag_run_id + task_id + try_number + state.
        """
        raw_body = await request.body()
        verify_airflow_signature(raw_body, signature)
        payload = json.loads(raw_body)
        timestamp_raw = payload.get("timestamp")
        try:
            callback_time = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
            if abs((_utcnow() - callback_time).total_seconds()) > 300:
                raise HTTPException(status_code=403, detail="Stale Airflow callback")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=422, detail="Invalid callback timestamp") from exc

        dag_run_id = payload.get("dag_run_id")
        task_key = payload.get("task_id")
        try_number = payload.get("try_number", 1)
        state_str = payload.get("state", "")

        tr = (
            db.query(TaskRun)
            .filter(
                TaskRun.dag_run_id == dag_run_id,
                TaskRun.airflow_task_id == task_key,
                TaskRun.try_number == try_number,
            )
            .first()
        )
        if not tr:
            logger.warning("Webhook: no task_run found for dag_run_id=%s task=%s try=%s", dag_run_id, task_key, try_number)
            return {"status": "not_found"}

        try:
            next_state = TaskRunState(state_str)
        except ValueError:
            return {"status": "unknown_state"}
        tr.state = next_state

        now = _utcnow()
        if state_str == "running" and not tr.started_at:
            tr.started_at = now
        if state_str in ("success", "failed", "skipped", "upstream_failed"):
            tr.ended_at = now
        tr.last_synced_at = now

        # Recompute parent run state
        run = tr.job_run
        if run and run.state != RunState.cancelled:
            latest_by_key = {}
            for task_run in run.task_runs:
                current = latest_by_key.get(task_run.task_key)
                if current is None or task_run.try_number > current.try_number:
                    latest_by_key[task_run.task_key] = task_run
            task_states = [task_run.state for task_run in latest_by_key.values()]
            if task_states and all(s == TaskRunState.success for s in task_states):
                run.state = RunState.success
                run.ended_at = now
            elif any(s == TaskRunState.up_for_retry for s in task_states):
                run.state = RunState.up_for_retry
                run.ended_at = None
            elif any(s in (TaskRunState.running, TaskRunState.queued) for s in task_states):
                run.state = RunState.running
                run.started_at = run.started_at or now
                run.ended_at = None
            elif any(s in (TaskRunState.failed, TaskRunState.upstream_failed) for s in task_states):
                run.state = RunState.failed
                run.ended_at = now
            run.last_synced_at = now

        db.commit()
        return {"status": "ok"}


def airflow_task_state(request, signature, db):
    return AirflowTaskState().execute(request, signature, db)
