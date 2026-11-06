from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.jobs.interfaces import SchedulerGateway
from app.jobs.models.job import AirflowJobSpec, JobStatus
from app.jobs.shared.support import _authorized_job, _utcnow, logger


class GetPublishStatus:
    def execute(self, job_id: str, gateway: SchedulerGateway, db: Session, guard: Guard):
        job = _authorized_job(db, guard, job_id, Privilege.BROWSE)
        spec = db.query(AirflowJobSpec).filter(AirflowJobSpec.job_id == job.job_id).first()
        if not spec:
            return {"state": "draft", "confirmed_at": None}
        try:
            if gateway.dag_exists(spec.dag_id):
                gateway.set_dag_paused(spec.dag_id, job.status != JobStatus.active)
                spec.publish_state = "active"
                if spec.airflow_confirmed_at is None:
                    spec.airflow_confirmed_at = _utcnow()
                db.commit()
        except Exception:
            logger.warning("Could not confirm Airflow DAG %s", spec.dag_id, exc_info=True)
        return {
            "state": spec.publish_state,
            "confirmed_at": spec.airflow_confirmed_at,
            "dag_id": spec.dag_id,
        }


def get_publish_status(job_id, gateway, db, guard):
    return GetPublishStatus().execute(job_id, gateway, db, guard)
