"""Orchestrate one ingestion run."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.ingestion.composition import execution_logger
from app.ingestion.models import IngestionRun, IngestionRunItem
from app.ingestion.run.application.execute_single_param import execute_single_param
from app.ingestion.run.application.resolve_param_values import resolve_param_values

logger = execution_logger()


class ExecuteRun:
    def execute(
        self,
        db: Session,
        job_config_id: UUID,
        workspace_id: UUID,
        airflow_dag_run_id: Optional[str] = None,
    ) -> IngestionRun:
        """
        Orchestrate a full ingestion run for one job config.
        Called by the /trigger API endpoint or the Airflow task.
        """
        from app.ingestion.job_configs import get_job_config
        from app.ingestion.connections import resolve_secret

        cfg = get_job_config(db, workspace_id, job_config_id)
        conn = cfg.connection
        secret = resolve_secret(db, conn)

        # Create run record
        run = IngestionRun(
            id=uuid4(),
            job_config_id=job_config_id,
            airflow_dag_run_id=airflow_dag_run_id,
            status="running",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

        # Resolve param values
        param_values = resolve_param_values(db, cfg, conn, secret)
        total_params = len(param_values)

        # Fan-out with bounded concurrency (D10)
        max_workers = min(conn.max_concurrency, total_params) or 1
        items: List[IngestionRunItem] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    execute_single_param, db, cfg, conn, secret, pv, run_id
                ): pv
                for pv in param_values
            }
            for future in as_completed(futures):
                item = future.result()
                db.add(item)
                items.append(item)

        db.commit()

        # Aggregate results
        succeeded = sum(1 for i in items if i.status == "succeeded")
        failed = sum(1 for i in items if i.status == "failed")

        if failed == 0:
            final_status = "succeeded"
        elif succeeded == 0:
            final_status = "failed"
        else:
            final_status = "partial"

        run.status = final_status
        run.finished_at = datetime.now(timezone.utc)
        run.total_params = total_params
        run.succeeded_params = succeeded
        run.failed_params = failed
        run.total_rows_landed = sum(i.rows_landed for i in items)
        run.total_bytes_landed = sum(i.bytes_landed for i in items)
        if failed > 0:
            errors = [i.error_message for i in items if i.error_message]
            run.error_summary = "; ".join(errors[:3])

        db.commit()
        db.refresh(run)
        logger.info(
            "Run %s finished: status=%s params=%d succeeded=%d failed=%d",
            run_id, final_status, total_params, succeeded, failed,
        )
        return run


def execute_run(
    db: Session,
    job_config_id: UUID,
    workspace_id: UUID,
    airflow_dag_run_id: Optional[str] = None,
) -> IngestionRun:
    return ExecuteRun().execute(db, job_config_id, workspace_id, airflow_dag_run_id)
