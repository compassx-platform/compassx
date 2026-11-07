import threading

from fastapi import HTTPException

from app.compute.shared.support import _run_service_action_async, _service_info, logger
from app.governance.dependencies import Guard
from services.airflow.manager import get_airflow_manager
from services.base import ServicePhase, ServiceStatus
from services.enterprise_gateway.manager import get_eg_manager
from services.minio.manager import get_minio_manager


class ControlComputeService:
    def execute(self, service_name: str, action: str, guard: Guard):
        guard.require_workspace_admin(f"Controlling the {service_name} service")

        managers = {
            "minio": ("MinIO", get_minio_manager()),
            "enterprise-gateway": ("Enterprise Gateway", get_eg_manager()),
            "airflow": ("Airflow", get_airflow_manager()),
        }
        actions = {"start", "stop", "restart"}

        if service_name not in managers:
            raise HTTPException(status_code=404, detail=f"Unknown compute service: {service_name}")
        if action not in actions:
            raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
        from app.platform_mode import ensure_deployed

        ensure_deployed(service_name)

        label, manager = managers[service_name]
        if service_name == "airflow":
            thread = threading.Thread(
                target=_run_service_action_async,
                args=(service_name, action, label, manager),
                daemon=True,
            )
            thread.start()
            return _service_info(
                service_name,
                label,
                ServiceStatus(
                    phase=ServicePhase.STARTING,
                    message=f"{label} {action} requested.",
                    details=manager.get_status().details,
                ),
            )

        status = getattr(manager, action)()
        if service_name == "minio" and action in {"start", "restart"}:
            try:
                manager.ensure_buckets()
            except Exception as exc:
                logger.warning("MinIO buckets ensure failed after %s: %s", action, exc)
        return _service_info(service_name, label, status)


def control_compute_service(service_name, action, guard):
    return ControlComputeService().execute(service_name, action, guard)
