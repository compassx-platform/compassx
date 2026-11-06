import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.jobs.models.run_trace import JobExecution
from app.jobs.security import verify_internal_secret


class ExecutionStatus:
    def execute(self, execution_id: str, secret: str | None, db: Session):
        verify_internal_secret(secret)
        execution = db.query(JobExecution).filter(
            JobExecution.execution_id == uuid.UUID(execution_id)
        ).first()
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        return {
            "execution_ref": str(execution.execution_id),
            "state": execution.state,
            "output_uri": execution.output_uri,
            "error": execution.error,
        }


def execution_status(execution_id, secret, db):
    return ExecutionStatus().execute(execution_id, secret, db)
