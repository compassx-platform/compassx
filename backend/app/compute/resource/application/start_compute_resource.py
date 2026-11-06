from fastapi import Request

from app.compute.shared.support import _caller, _error, _require_compute, _service, logger
from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.services.sandbox_reaper_service import unified_reaper_service


class StartComputeResource:
    def execute(self, req_context: Request, resource_id: str, db, guard: Guard):
        user_id, workspace_id = _caller(req_context, guard)
        _require_compute(guard, db, resource_id, Privilege.USE_COMPUTE)
        try:
            service = _service(req_context, db)
            unified_reaper_service.touch_compute_activity(resource_id)
            return service.start_resource(resource_id, user_id, workspace_id=workspace_id)
        except ValueError as exc:
            return _error("NotFound", str(exc), 404)
        except Exception as exc:
            logger.exception("Error starting compute resource")
            return _error("InternalError", str(exc), 500)


def start_compute_resource(req_context, resource_id, db, guard):
    return StartComputeResource().execute(req_context, resource_id, db, guard)
