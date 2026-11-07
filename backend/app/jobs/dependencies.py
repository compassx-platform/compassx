"""Jobs application dependencies."""

from __future__ import annotations

from fastapi import Request

from app.jobs.interfaces import SchedulerGateway
from services.airflow.client import AirflowSchedulerGateway


def get_scheduler_gateway(request: Request) -> SchedulerGateway:
    from app.platform_mode import ensure_deployed

    ensure_deployed("airflow")
    gateway = getattr(request.app.state, "scheduler_gateway", None)
    if gateway is None:
        gateway = AirflowSchedulerGateway()
        request.app.state.scheduler_gateway = gateway
    return gateway
