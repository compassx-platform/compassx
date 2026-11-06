"""Fail executions left queued or running after a backend restart."""
from __future__ import annotations

import asyncio
import logging

from app.database import SystemSessionLocal
from app.jobs.models.run_trace import JobExecution
from app.jobs.security import utcnow

logger = logging.getLogger("app.jobs.execution_service")


class RecoverOrphanedExecutions:
    def execute(self, runtime_manager) -> int:
        """Fail and clean executions whose owning backend process was restarted."""
        db = SystemSessionLocal()
        recovered = 0
        try:
            executions = (
                db.query(JobExecution)
                .filter(JobExecution.state.in_(["queued", "running"]))
                .all()
            )
            for execution in executions:
                execution.state = "failed"
                execution.error = "Execution interrupted because the backend restarted."
                execution.ended_at = utcnow()
                db.commit()
                if execution.runtime_id:
                    try:
                        asyncio.run(runtime_manager.delete_runtime(execution.runtime_id))
                    except Exception:
                        logger.warning(
                            "Could not remove orphaned job runtime %s",
                            execution.runtime_id,
                            exc_info=True,
                        )
                recovered += 1
            return recovered
        finally:
            db.close()


def recover_orphaned_executions(runtime_manager) -> int:
    return RecoverOrphanedExecutions().execute(runtime_manager)
